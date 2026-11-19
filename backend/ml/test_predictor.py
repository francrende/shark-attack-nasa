"""Suite de pruebas unitarias e integración para ML-4 y ML-5 (``backend/ml/predictor.py``)."""

from __future__ import annotations

import time
import unittest
from datetime import date, timedelta

import numpy as np
import pandas as pd

from backend.ml import calibracion, departamentos, escenarios, rinde
from backend.ml.predictor import (
    CAMPOS_DISTRIBUCION_PREDICTIVA,
    CURRENT_FEATURES,
    DEFAULT_UMBRAL_DESFAVORABLE,
    FUTURE_FEATURES,
    NUMERIC_FEATURES,
    REQUIRED_FUTURE_FEATURES,
    THERMAL_RISK_THRESHOLDS,
    AgroPredictor,
    apply_what_if_simulation,
    build_ensemble_risk_sentence,
    classify_crop_risk,
    classify_summer_thermal_risk,
    crop_prose_name,
    crop_with_article,
    compute_hybrid_final_score,
    detect_physical_anomalies,
    escalate_risk_level,
    get_predictor,
    representative_scenario,
    run_recommendation,
    weighted_percentile,
)
from backend.providers.features import FEATURES_ACTUALES, FEATURES_PERIODO_CRITICO, features_ventana
from backend.services.rotation_matrix import evaluate_campaign_soil, penalizacion_demanda_hidrica


# Fecha de evaluación fija (= default de run_recommendation): define dias_hasta_siembra.
FECHA = date(2026, 11, 8)


class TestAgroPredictorML4(unittest.TestCase):
    """Verifica inferencia online, MCDA, anomalías, What-If y contrato JSON de backend/schemas.py."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.predictor = get_predictor()
        cls.context_drought_features: dict[str, float] = {
            "gwetroot_saturacion_pct": 34.0,
            "gwettop_saturacion_pct": 28.5,
            "tendencia_humedad_15d_pct": -12.0,
            "anomalia_lluvia_90d_pct": -24.2,
            "frecuencia_tormentas_extremas": 1.0,
            "frecuencia_estres_termico": 6.0,
            "frecuencia_riesgo_helada": 0.0,
            "indice_aridez_evaporativa": 0.52,
            "pendiente_terreno_pct": 1.8,
            "elevacion_m": 78.5,
            "textura_arcilla_pct": 24.5,
        }

    def test_01_singleton_and_model_bundle_loaded(self) -> None:
        p2 = get_predictor()
        self.assertIs(self.predictor, p2)
        self.assertIsInstance(self.predictor, AgroPredictor)
        self.assertEqual(len(self.predictor.feature_columns), 15)  # ML-7
        self.assertEqual(self.predictor.model_version, "ml10-magyp")
        self.assertEqual(len(self.predictor.crops_catalog["by_name"]), 11)

    def test_02_context_md_benchmark_contract_and_ranking(self) -> None:
        """Verifica que el caso testigo (−33,95, −60,57, antecesor soja de primera) reproduzca ranking, riesgos y estructura."""
        resp = run_recommendation(
            features=self.context_drought_features,
            campana="verano",
            cultivo_anterior="soja_primera",
            objetivo_productor="equilibrio",
            carbono_organico_g_kg=18.4,
            ubicacion={"lat": -33.95, "lon": -60.57},
        )

        # Bloques obligatorios del contrato de /simulate
        for key in (
            "ubicacion",
            "telemetria_nasa",
            "topografia_srtm",
            "perfil_suelo",
            "anomalias_detectadas",
            "recomendacion_principal",
            "ranking_cultivos",
            "validacion_local_requerida",
            "cobertura_12_meses",
            "comparacion_estrategias",
        ):
            self.assertIn(key, resp)

        # ML-7 (rindes reales): se verifica estructura y coherencia, no los valores de la fórmula FAO.
        rec = resp["recomendacion_principal"]
        ranking = resp["ranking_cultivos"]
        self.assertEqual(rec["cultivo"], ranking[0]["cultivo"])
        self.assertEqual(rec["score_final"], ranking[0]["score_final"])
        self.assertEqual(len(rec["factores_clave_ml"]), 3)
        self.assertIn(f"Recomendación: Sembrar {crop_prose_name(rec['cultivo'])}", rec["explicacion"])
        self.assertEqual(len(ranking), 6)
        # Primero los sembrables (por puntaje), después los que ya pasaron su ventana de siembra.
        claves = [(item["motivo_no_sembrable"] is not None, -item["score_final"]) for item in ranking]
        self.assertEqual(claves, sorted(claves))
        self.assertIsNone(ranking[0]["motivo_no_sembrable"])
        for item in ranking:
            self.assertTrue(0.0 <= item["score_final"] <= 100.0)
            self.assertIn(item["riesgo"], ("bajo", "medio", "alto", "critico"))
            self.assertIn("fuera_de_ventana_siembra", item)
        # El suelo no depende del modelo: el sorgo tras soja sigue en 95 (matriz ML-3)
        soil = evaluate_campaign_soil("verano", "soja_primera", 18.4, 1.8, 24.5, None)
        self.assertEqual(round(float(soil["sorgo"].s_suelo), 1), 95.0)
        # Repetir soja (monocultivo) queda último entre los sembrables por el pilar suelo
        sembrables = [item["cultivo"] for item in ranking if item["motivo_no_sembrable"] is None]
        self.assertEqual(sembrables[-1], "soja_primera")

    def test_03_what_if_internal_coupling_and_independent_controls(self) -> None:
        """Verifica que los sliders What-If sean independientes pero mantengan consistencia física."""
        # A) Solo variación de lluvia (+30%) -> actualiza anomalía, índice de aridez y humedad acoplada
        # Multiplicativa: (100 - 24.2) * 1.30 - 100 = -1.46 (llueve 30% más que lo observado)
        sim_rain = apply_what_if_simulation(
            self.context_drought_features,
            override_humedad_radicular_pct=None,
            variacion_lluvia_esperada_pct=30.0,
        )
        self.assertAlmostEqual(sim_rain["anomalia_lluvia_90d_pct"], -1.46, places=2)
        sim_dry = apply_what_if_simulation(
            self.context_drought_features, variacion_lluvia_esperada_pct=-40.0
        )
        self.assertAlmostEqual(sim_dry["anomalia_lluvia_90d_pct"], 75.8 * 0.6 - 100.0, places=2)
        self.assertGreater(
            sim_rain["indice_aridez_evaporativa"],
            self.context_drought_features["indice_aridez_evaporativa"],
        )
        self.assertGreater(
            sim_rain["gwetroot_saturacion_pct"],
            self.context_drought_features["gwetroot_saturacion_pct"],
        )

        # B) Override explícito de humedad radicular (72%) sin cambiar lluvia
        sim_moist = apply_what_if_simulation(
            self.context_drought_features,
            override_humedad_radicular_pct=72.0,
            variacion_lluvia_esperada_pct=0.0,
        )
        self.assertEqual(sim_moist["gwetroot_saturacion_pct"], 72.0)
        self.assertEqual(
            sim_moist["anomalia_lluvia_90d_pct"],
            self.context_drought_features["anomalia_lluvia_90d_pct"],
        )
        self.assertGreater(
            sim_moist["gwettop_saturacion_pct"],
            self.context_drought_features["gwettop_saturacion_pct"],
        )

        # C) En escenario húmedo + perfil recargado, maiz_temprano sube fuertemente su aptitud
        resp_drought = run_recommendation(self.context_drought_features, campana="verano")
        resp_wet = run_recommendation(
            self.context_drought_features,
            campana="verano",
            simulacion_what_if={
                "override_humedad_radicular_pct": 70.0,
                "variacion_lluvia_esperada_pct": 30.0,
            },
        )
        maiz_drought = next(
            r["score_final"] for r in resp_drought["ranking_cultivos"] if r["cultivo"] == "maiz_temprano"
        )
        maiz_wet = next(
            r["score_final"] for r in resp_wet["ranking_cultivos"] if r["cultivo"] == "maiz_temprano"
        )
        self.assertGreater(maiz_wet, maiz_drought)  # ML-7: dirección, no magnitud FAO

    def test_04_all_six_evidence_based_anomalies(self) -> None:
        """Verifica la activación del catálogo de 6 anomalías físicas basadas en evidencia."""
        # 1, 2 y 4: Déficit radicular + Flash Drought + Escorrentía en pendiente en el caso testigo
        anom_drought = detect_physical_anomalies(
            self.context_drought_features, campana="verano", cultivo_anterior="soja_primera"
        )
        tipos_drought = {a["tipo"] for a in anom_drought}
        self.assertIn("deficit_hidrico_radicular", tipos_drought)
        self.assertIn("pulso_secado_rapido", tipos_drought)
        self.assertIn("riesgo_escorrentia_erosion", tipos_drought)

        # 3: Trampa de Falsa Recarga Superficial (GWETTOP alto y GWETROOT bajo)
        false_recharge_feat = dict(self.context_drought_features)
        false_recharge_feat["gwettop_saturacion_pct"] = 68.0
        false_recharge_feat["gwetroot_saturacion_pct"] = 31.0
        anom_false = detect_physical_anomalies(false_recharge_feat, campana="verano")
        self.assertIn("falsa_recarga_superficial", {a["tipo"] for a in anom_false})

        # 5 y 6: Exceso Hídrico / Anegamiento + Estrés Térmico Crítico
        waterlog_feat = dict(self.context_drought_features)
        waterlog_feat["gwetroot_saturacion_pct"] = 89.0
        waterlog_feat["anomalia_lluvia_90d_pct"] = 45.0
        waterlog_feat["frecuencia_estres_termico"] = 30.0
        anom_wet = detect_physical_anomalies(waterlog_feat, campana="verano")
        tipos_wet = {a["tipo"] for a in anom_wet}
        self.assertIn("exceso_hidrico_anegamiento", tipos_wet)
        self.assertIn("estres_termico_critico", tipos_wet)

    def test_05_objectives_and_limiting_factor_penalty(self) -> None:
        """Verifica los pesos dinámicos por objetivo y la penalización Opción B (< 35)."""
        # Sin pilar crítico (>= 35): lineal puro
        self.assertEqual(compute_hybrid_final_score(80.0, 60.0, "equilibrio"), 70.0)
        self.assertEqual(compute_hybrid_final_score(80.0, 60.0, "resiliencia_hidroclimatica"), 75.0)
        self.assertEqual(compute_hybrid_final_score(80.0, 60.0, "conservacion_suelo"), 66.0)

        # Con pilar crítico (< 35): aplica penalización de cuello de botella
        score_penalized = compute_hybrid_final_score(56.2, 13.0, "equilibrio")
        self.assertLess(score_penalized, (56.2 + 13.0) / 2.0)
        self.assertAlmostEqual(score_penalized, 31.0, places=1)

    def test_06_winter_campaign_and_enriched_metadata(self) -> None:
        """Verifica campaña de invierno, cobertura 12m y comparador de estrategias."""
        winter_features = dict(self.context_drought_features)
        winter_features["frecuencia_estres_termico"] = 0.0
        winter_features["frecuencia_riesgo_helada"] = 9.0

        resp = run_recommendation(
            features=winter_features,
            campana="invierno",
            cultivo_anterior="soja_primera",
            objetivo_productor="conservacion_suelo",
        )
        self.assertEqual(len(resp["ranking_cultivos"]), 5)
        self.assertEqual(len(resp["cobertura_12_meses"]["calendario"]), 12)
        self.assertEqual(len(resp["comparacion_estrategias"]), 3)
        for strat in resp["comparacion_estrategias"]:
            self.assertIn("score_final", strat)
            self.assertGreaterEqual(strat["score_final"], 0.0)
            self.assertLessEqual(strat["score_final"], 100.0)

    def test_07_full_pipeline_latency_under_15ms(self) -> None:
        """Verifica que el pipeline completo (ML + Matriz + Anomalías + Explicación) corra en < 15 ms."""
        # Warm-up
        for _ in range(5):
            run_recommendation(self.context_drought_features, campana="verano")

        timings_ms: list[float] = []
        for _ in range(100):
            t0 = time.perf_counter()
            run_recommendation(self.context_drought_features, campana="verano")
            timings_ms.append((time.perf_counter() - t0) * 1000.0)

        p95_ms = float(np.percentile(timings_ms, 95))
        self.assertLess(p95_ms, 15.0, f"Latencia p95 ({p95_ms:.2f} ms) superó el límite de 15 ms")


# Escenarios históricos con la forma exacta de InsumosML.escenarios_historicos (BACK-6).
# Rango parecido al de Pergamino al 11/11/2026: calor de 1 a 45 días, tormentas 0-2, heladas 0.
_HEAT_DAYS = [1, 3, 5, 6, 8, 10, 12, 14, 16, 18, 21, 23, 25, 28, 31, 34, 38, 41, 45]
ENSEMBLE_SCENARIOS: list[dict[str, int]] = [
    {
        "anio": 2006 + i,
        "frecuencia_tormentas_extremas": i % 3,
        "frecuencia_estres_termico": heat,
        "frecuencia_riesgo_helada": 0,
        "lluvia_periodo_critico_mm": 320.0 - 5.0 * heat,
    }
    for i, heat in enumerate(_HEAT_DAYS)
]


class TestEnsembleML5(unittest.TestCase):
    """Verifica el ensemble de años análogos de la ventana futura (ML-5)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.predictor = get_predictor()
        # Las 8 features actuales del caso testigo (sin la ventana futura)
        cls.current: dict[str, float] = {
            "gwetroot_saturacion_pct": 34.0,
            "gwettop_saturacion_pct": 28.5,
            "tendencia_humedad_15d_pct": -12.0,
            "anomalia_lluvia_90d_pct": -24.2,
            "indice_aridez_evaporativa": 0.52,
            "pendiente_terreno_pct": 1.8,
            "elevacion_m": 78.5,
            "textura_arcilla_pct": 24.5,
        }

    def _ens(self, *args, **kwargs):
        kwargs.setdefault("fecha_corte", FECHA)
        return self.predictor.predict_ensemble(*args, **kwargs)

    def _batch(self, *args, **kwargs):
        kwargs.setdefault("fecha_corte", FECHA)
        return self.predictor.predict_hydroclimatic_batch(*args, **kwargs)

    def _individual_scores(self, campana: str = "verano") -> dict[str, list[float]]:
        """Score sin redondear de cada escenario, predicho fila por fila (referencia)."""
        p = self.predictor
        crops = list(self._batch({**self.current, **{f: 0.0 for f in FUTURE_FEATURES}}, campana=campana))
        out: dict[str, list[float]] = {c: [] for c in crops}
        for esc in ENSEMBLE_SCENARIOS:
            vec = {**self.current, **{f: float(esc[f]) for f in FUTURE_FEATURES}}
            X = np.asarray(
                [p._fila({**vec, **p._contexto_cultivo(c, campana, FECHA)}, c, campana) for c in crops]
            )
            gwetroot = self.current["gwetroot_saturacion_pct"]
            for c, s in zip(crops, self.predictor._predict_clipped(X)):
                # ML-10: el puntaje público descuenta la demanda hídrica con perfil seco.
                out[c].append(float(np.clip(s - penalizacion_demanda_hidrica(c, gwetroot), 0.0, 100.0)))
        return out

    def test_01_feature_names_match_backend(self) -> None:
        """Las features actuales/futuras del ML coinciden con las de providers/features.py."""
        self.assertEqual(tuple(CURRENT_FEATURES), tuple(FEATURES_ACTUALES))
        self.assertEqual(tuple(FUTURE_FEATURES), tuple(FEATURES_PERIODO_CRITICO))
        self.assertEqual(
            set(CURRENT_FEATURES) | set(FUTURE_FEATURES) | {"dias_hasta_siembra", "oni_actual"},
            set(NUMERIC_FEATURES),
        )
        self.assertEqual(tuple(self.predictor.feature_columns[:-1]), tuple(NUMERIC_FEATURES))

    def test_02_single_scenario_matches_batch(self) -> None:
        """Con un solo escenario, el ensemble es idéntico a la predicción de vector único."""
        esc = ENSEMBLE_SCENARIOS[4]
        ens = self._ens(self.current, [esc], "verano")
        batch = self._batch(
            {**self.current, **{f: float(esc[f]) for f in FUTURE_FEATURES}}, campana="verano"
        )
        self.assertEqual(set(ens), set(batch))
        for crop, score in batch.items():
            self.assertEqual(ens[crop]["promedio"], score)
            self.assertEqual(ens[crop]["p10"], score)
            self.assertEqual(ens[crop]["p90"], score)
            self.assertEqual(ens[crop]["anios_evaluados"], 1)

    def test_03_aggregates_match_numpy(self) -> None:
        """Promedio, P10, P90, años desfavorables y peor escenario coinciden con numpy."""
        ens = self._ens(self.current, ENSEMBLE_SCENARIOS, "verano")
        ref = self._individual_scores()
        for crop, scores in ref.items():
            arr = np.asarray(scores)
            dist = ens[crop]
            self.assertAlmostEqual(dist["promedio"], round(float(arr.mean()), 1), places=6)
            self.assertAlmostEqual(dist["p10"], round(float(np.percentile(arr, 10)), 1), places=6)
            self.assertAlmostEqual(dist["p90"], round(float(np.percentile(arr, 90)), 1), places=6)
            self.assertEqual(dist["anios_desfavorables"], int(np.sum(arr < DEFAULT_UMBRAL_DESFAVORABLE)))
            self.assertEqual(dist["anios_evaluados"], len(ENSEMBLE_SCENARIOS))
            self.assertEqual(dist["umbral_desfavorable"], DEFAULT_UMBRAL_DESFAVORABLE)
            worst = ENSEMBLE_SCENARIOS[int(np.argmin(arr))]
            self.assertEqual(dist["peor_escenario"]["anio"], worst["anio"])
            self.assertAlmostEqual(dist["peor_escenario"]["score"], round(float(arr.min()), 1))
            for f in REQUIRED_FUTURE_FEATURES:
                self.assertEqual(dist["peor_escenario"][f], worst[f])
            self.assertLessEqual(dist["p10"], dist["promedio"] + 1e-9)
            self.assertLessEqual(dist["promedio"], dist["p90"] + 1e-9)

    def test_04_threshold_is_configurable(self) -> None:
        """El conteo de años desfavorables respeta umbral_desfavorable."""
        ref = self._individual_scores()
        for umbral in (0.0, 65.0, 101.0):
            ens = self._ens(
                self.current, ENSEMBLE_SCENARIOS, "verano", umbral_desfavorable=umbral
            )
            for crop, scores in ref.items():
                self.assertEqual(
                    ens[crop]["anios_desfavorables"], int(np.sum(np.asarray(scores) < umbral))
                )
                self.assertEqual(ens[crop]["umbral_desfavorable"], umbral)

    def test_05_weights(self) -> None:
        """Pesos uniformes = sin pesos; peso 0 descarta el escenario; pesos cambian el promedio."""
        base = self._ens(self.current, ENSEMBLE_SCENARIOS, "verano")
        uniform = self._ens(
            self.current, ENSEMBLE_SCENARIOS, "verano", pesos=[2.5] * len(ENSEMBLE_SCENARIOS)
        )
        self.assertEqual(base, uniform)

        pesos = [1.0] * len(ENSEMBLE_SCENARIOS)
        pesos[-1] = 0.0
        dropped = self._ens(
            self.current, ENSEMBLE_SCENARIOS, "verano", pesos=pesos
        )
        expected = self._ens(self.current, ENSEMBLE_SCENARIOS[:-1], "verano")
        self.assertEqual(dropped, expected)

        # Ponderar fuerte los años más calurosos baja el promedio de los cultivos sensibles al calor
        heavy_hot = [1.0 + 10.0 * (esc["frecuencia_estres_termico"] >= 30) for esc in ENSEMBLE_SCENARIOS]
        hot = self._ens(
            self.current, ENSEMBLE_SCENARIOS, "verano", pesos=heavy_hot
        )
        self.assertLess(hot["maiz_temprano"]["promedio"], base["maiz_temprano"]["promedio"])

        # Percentil ponderado: con pesos iguales replica numpy (método linear)
        vals = [5.0, 1.0, 9.0, 3.0, 7.0]
        for q in (0, 10, 37.5, 50, 90, 100):
            self.assertAlmostEqual(
                weighted_percentile(vals, q, [1.0] * 5), float(np.percentile(vals, q))
            )
        self.assertEqual(weighted_percentile([4.0], 10, [3.0]), 4.0)

    def test_06_validation_errors(self) -> None:
        """Entradas inválidas lanzan ValueError."""
        with self.assertRaises(ValueError):
            self._ens(self.current, [], "verano")
        incomplete_current = dict(self.current)
        del incomplete_current["elevacion_m"]
        with self.assertRaises(ValueError):
            self._ens(incomplete_current, ENSEMBLE_SCENARIOS, "verano")
        bad_esc = [{"anio": 2010, "frecuencia_tormentas_extremas": 1, "frecuencia_estres_termico": 4}]
        with self.assertRaises(ValueError):
            self._ens(self.current, bad_esc, "verano")
        for pesos in ([1.0, 2.0], [0.0] * len(ENSEMBLE_SCENARIOS), [-1.0] + [1.0] * 18):
            with self.assertRaises(ValueError):
                self._ens(self.current, ENSEMBLE_SCENARIOS, "verano", pesos=pesos)

    def test_07_risk_escalation_by_p10(self) -> None:
        """El riesgo sube un nivel solo si el P10 cae por debajo de 30 (ML-8)."""
        self.assertEqual(escalate_risk_level("bajo", 30.0), "bajo")
        self.assertEqual(escalate_risk_level("bajo", 29.9), "medio")
        self.assertEqual(escalate_risk_level("medio", 10.0), "alto")
        self.assertEqual(escalate_risk_level("alto", 10.0), "critico")
        self.assertEqual(escalate_risk_level("critico", 10.0), "critico")

        resp = run_recommendation(
            self.current, campana="verano", escenarios_historicos=ENSEMBLE_SCENARIOS
        )
        ens = self._ens(self.current, ENSEMBLE_SCENARIOS, "verano")
        soil = evaluate_campaign_soil(
            campana="verano",
            cultivo_anterior="soja_primera",
            carbono_organico_g_kg=18.4,
            pendiente_terreno_pct=self.current["pendiente_terreno_pct"],
            arcilla_pct=self.current["textura_arcilla_pct"],
            phh2o=None,
        )
        escalated = 0
        for item in resp["ranking_cultivos"]:
            crop = item["cultivo"]
            base_risk = classify_crop_risk(ens[crop]["promedio"], round(float(soil[crop].s_suelo), 1))
            self.assertEqual(item["riesgo"], escalate_risk_level(base_risk, ens[crop]["p10"]))
            escalated += item["riesgo"] != base_risk
        self.assertGreaterEqual(escalated, 0)

    def test_08_contract_without_scenarios_is_unchanged(self) -> None:
        """Sin escenarios, la respuesta no trae ningún campo nuevo de ML-5."""
        full_features = {**self.current, "frecuencia_tormentas_extremas": 1.0,
                         "frecuencia_estres_termico": 6.0, "frecuencia_riesgo_helada": 0.0}
        resp = run_recommendation(full_features, campana="verano")
        self.assertNotIn("distribucion_hidroclimatica", resp["recomendacion_principal"])
        self.assertEqual(
            list(resp["recomendacion_principal"]),
            ["cultivo", "secuencia_sugerida", "score_final", "sub_scores",
             "perfil_mercado", "factores_clave_ml", "explicacion"],
        )
        for item in resp["ranking_cultivos"]:
            self.assertEqual(set(item), {"cultivo", "score_final", "riesgo", "sub_scores", "fuera_de_ventana_siembra", "motivo_no_sembrable"})

    def test_09_contract_with_scenarios(self) -> None:
        """Con escenarios, S_hidro es el promedio y se agregan los campos del contrato §5."""
        resp = run_recommendation(
            self.current, campana="verano", escenarios_historicos=ENSEMBLE_SCENARIOS
        )
        ens = self._ens(self.current, ENSEMBLE_SCENARIOS, "verano")
        rec = resp["recomendacion_principal"]
        winner = rec["cultivo"]
        # rinde_kg_ha (ML-17) depende de la ubicación, que _ens no pasa: se compara aparte.
        sin_rinde = lambda d: {k: v for k, v in d.items() if k != "rinde_kg_ha"}  # noqa: E731
        self.assertEqual(sin_rinde(rec["distribucion_hidroclimatica"]), sin_rinde(ens[winner]))
        self.assertEqual(rec["rinde_kg_ha"], rec["distribucion_hidroclimatica"]["rinde_kg_ha"])
        self.assertEqual(rec["sub_scores"]["hidroclimatico"], ens[winner]["promedio"])
        self.assertIn("años análogos", rec["explicacion"])
        self.assertIn(build_ensemble_risk_sentence(ens[winner]), rec["explicacion"])
        for item in resp["ranking_cultivos"]:
            dist = ens[item["cultivo"]]
            self.assertEqual(item["score_hidroclimatico_p10"], dist["p10"])
            self.assertEqual(item["anios_desfavorables"], dist["anios_desfavorables"])
            self.assertEqual(item["anios_evaluados"], len(ENSEMBLE_SCENARIOS))
        for strat in resp["comparacion_estrategias"]:
            self.assertEqual(strat["s_hidroclimatico"], ens[strat["cultivo_evaluado"]]["promedio"])

        # Las anomalías usan el escenario representativo (mediana por feature)
        rep = representative_scenario(ENSEMBLE_SCENARIOS)
        self.assertEqual(rep["frecuencia_estres_termico"], float(np.median(_HEAT_DAYS)))
        self.assertEqual(
            resp["telemetria_nasa"]["frecuencia_tormentas_extremas_90d"],
            int(rep["frecuencia_tormentas_extremas"]),
        )

    def test_10_what_if_applies_to_every_scenario(self) -> None:
        """El What-If modifica el presente de cada escenario y mantiene el futuro incierto."""
        what_if = {"override_humedad_radicular_pct": 75.0, "variacion_lluvia_esperada_pct": 30.0}
        ens = self._ens(
            self.current, ENSEMBLE_SCENARIOS, "verano", simulacion_what_if=what_if
        )
        expected_promedios: dict[str, list[float]] = {}
        for esc in ENSEMBLE_SCENARIOS:
            vec = apply_what_if_simulation(
                {**self.current, **{f: float(esc[f]) for f in FUTURE_FEATURES}},
                override_humedad_radicular_pct=75.0,
                variacion_lluvia_esperada_pct=30.0,
            )
            for crop, s in self._batch(vec, "verano").items():
                expected_promedios.setdefault(crop, []).append(s)
        for crop, scores in expected_promedios.items():
            self.assertAlmostEqual(ens[crop]["promedio"], float(np.mean(scores)), delta=0.1)
        self.assertGreater(ens["maiz_temprano"]["promedio"], self._ens(
            self.current, ENSEMBLE_SCENARIOS, "verano")["maiz_temprano"]["promedio"])

    def test_11_winter_campaign(self) -> None:
        """El ensemble funciona igual para invierno (5 cultivos)."""
        winter = [dict(e, frecuencia_estres_termico=0, frecuencia_riesgo_helada=5 + i)
                  for i, e in enumerate(ENSEMBLE_SCENARIOS)]
        ens = self._ens(self.current, winter, "invierno")
        self.assertEqual(len(ens), 5)
        resp = run_recommendation(self.current, campana="invierno", escenarios_historicos=winter)
        self.assertEqual(len(resp["ranking_cultivos"]), 5)

    def test_12_ensemble_latency_under_15ms(self) -> None:
        """Pipeline completo con ensemble (6 cultivos × 20 escenarios) con p95 < 15 ms."""
        scenarios_20 = ENSEMBLE_SCENARIOS + [dict(ENSEMBLE_SCENARIOS[0], anio=2025)]
        for _ in range(5):
            run_recommendation(self.current, campana="verano", escenarios_historicos=scenarios_20)
        timings_ms: list[float] = []
        for _ in range(100):
            t0 = time.perf_counter()
            run_recommendation(self.current, campana="verano", escenarios_historicos=scenarios_20)
            timings_ms.append((time.perf_counter() - t0) * 1000.0)
        p95_ms = float(np.percentile(timings_ms, 95))
        self.assertLess(p95_ms, 15.0, f"Latencia p95 ensemble ({p95_ms:.2f} ms) superó 15 ms")



class TestConsistenciaTextos(unittest.TestCase):
    """Arreglos post BACK-7: escala térmica única y redacción de la explicación."""

    def test_escala_termica(self) -> None:
        # Paridad con providers.nasa_telemetry en routers/test_simulate.py
        self.assertEqual(THERMAL_RISK_THRESHOLDS, (15.0, 25.0, 40.0))
        esperado = {0: "bajo", 14: "bajo", 15: "medio", 21: "medio", 25: "alto", 40: "alto", 41: "critico"}
        for dias, nivel in esperado.items():
            self.assertEqual(classify_summer_thermal_risk(dias), nivel, dias)

    def test_anomalia_termica_solo_con_riesgo_alto_o_critico(self) -> None:
        base = {f: 50.0 for f in NUMERIC_FEATURES}
        base.update(gwetroot_saturacion_pct=55.0, gwettop_saturacion_pct=50.0,
                    tendencia_humedad_15d_pct=0.0, anomalia_lluvia_90d_pct=0.0,
                    indice_aridez_evaporativa=1.0, pendiente_terreno_pct=0.5,
                    textura_arcilla_pct=24.0, frecuencia_tormentas_extremas=0.0,
                    frecuencia_riesgo_helada=0.0)
        esperado = {21: None, 25: "media", 40: "media", 45: "alta"}
        for dias, sev in esperado.items():
            anomalias = detect_physical_anomalies({**base, "frecuencia_estres_termico": float(dias)}, campana="verano")
            termica = [a for a in anomalias if a["tipo"] == "estres_termico_critico"]
            if sev is None:
                self.assertEqual(termica, [], dias)
            else:
                self.assertEqual(termica[0]["severidad"], sev, dias)

    def test_explicacion_sin_de_el(self) -> None:
        features = {
            "gwetroot_saturacion_pct": 15.0, "gwettop_saturacion_pct": 20.0,
            "tendencia_humedad_15d_pct": -14.0, "anomalia_lluvia_90d_pct": -60.0,
            "frecuencia_tormentas_extremas": 0.0, "frecuencia_estres_termico": 21.0,
            "frecuencia_riesgo_helada": 0.0, "indice_aridez_evaporativa": 0.45,
            "pendiente_terreno_pct": 0.8, "elevacion_m": 69.0, "textura_arcilla_pct": 23.4,
        }
        resp = run_recommendation(features, campana="verano", cultivo_anterior="soja_primera")
        self.assertNotIn(" de el ", resp["recomendacion_principal"]["explicacion"])
        # Contracción con un ganador fijo (no depende de qué cultivo elija el modelo)
        crops = ["sorgo", "maiz_tardio", "girasol", "maiz_temprano", "soja_segunda", "soja_primera"]
        subs = {c: {"hidroclimatico": 50.0 - i, "suelo": 80.0 - i} for i, c in enumerate(crops)}
        ranking = [{"cultivo": c, "score_final": 60.0 - i} for i, c in enumerate(crops)]
        explicacion = get_predictor().build_explanation("sorgo", "maiz_tardio", ranking, subs, features, "soja_primera")
        self.assertNotIn(" de el ", explicacion)
        self.assertIn("A diferencia del Maíz Temprano", explicacion)

    def test_explicacion_invierno_genero_y_sin_parentesis_anidados(self) -> None:
        features = {
            "gwetroot_saturacion_pct": 46.0, "gwettop_saturacion_pct": 35.0,
            "tendencia_humedad_15d_pct": -4.4, "anomalia_lluvia_90d_pct": -37.4,
            "frecuencia_tormentas_extremas": 0.0, "frecuencia_estres_termico": 0.0,
            "frecuencia_riesgo_helada": 10.0, "indice_aridez_evaporativa": 0.75,
            "pendiente_terreno_pct": 0.8, "elevacion_m": 69.0, "textura_arcilla_pct": 23.4,
        }
        resp = run_recommendation(features, campana="invierno", cultivo_anterior="maiz_tardio")
        explicacion = resp["recomendacion_principal"]["explicacion"]
        ganador = resp["recomendacion_principal"]["cultivo"]
        self.assertNotIn("(Cultivo de Cobertura)", explicacion)
        self.assertNotIn("repetir Maíz Tardío", explicacion)  # anterior de otra campaña
        self.assertIn(f"{crop_with_article(ganador)} tiene un rinde esperado", explicacion.replace("La ", "la "))
        self.assertIn(f"Sembrar {crop_prose_name(ganador)}", explicacion)

    def test_articulos_por_cultivo(self) -> None:
        self.assertEqual(crop_with_article("vicia_cobertura"), "la Vicia de cobertura")
        self.assertEqual(crop_with_article("soja_primera"), "la Soja de Primera")
        self.assertEqual(crop_with_article("trigo"), "el Trigo")
        self.assertEqual(crop_with_article("maiz_tardio"), "el Maíz Tardío")


class TestCoberturasYDemandaHidricaML10(unittest.TestCase):
    """ML-10: coberturas fuera del modelo (Ky relativo) y penalización por demanda hídrica."""

    SIN_RINDE = ("vicia_cobertura", "avena_cobertura", "camelina")

    @classmethod
    def setUpClass(cls) -> None:
        cls.predictor = get_predictor()

    def _features(self, gwetroot: float, anomalia: float) -> dict[str, float]:
        return {
            "gwetroot_saturacion_pct": gwetroot, "gwettop_saturacion_pct": gwetroot,
            "tendencia_humedad_15d_pct": 0.0, "anomalia_lluvia_90d_pct": anomalia,
            "frecuencia_tormentas_extremas": 0.0, "frecuencia_estres_termico": 3.0,
            "frecuencia_riesgo_helada": 3.0, "indice_aridez_evaporativa": 0.35 if anomalia < 0 else 1.2,
            "lluvia_periodo_critico_mm": 250.0, "pendiente_terreno_pct": 0.5,
            "elevacion_m": 80.0, "textura_arcilla_pct": 25.0,
        }

    def _batch(self, features: dict[str, float]) -> dict[str, float]:
        return self.predictor.predict_hydroclimatic_batch(
            features, campana="invierno", fecha_corte=date(2026, 5, 1), oni_actual=-1.0 if features["anomalia_lluvia_90d_pct"] < 0 else 0.0
        )

    def test_modelo_solo_entrena_cultivos_con_rinde(self) -> None:
        self.assertEqual(
            self.predictor.cultivos_entrenados,
            {"trigo", "cebada", "maiz_temprano", "maiz_tardio", "soja_primera", "soja_segunda", "girasol", "sorgo"},
        )

    def test_coberturas_no_se_hunden_en_sequia(self) -> None:
        """Con perfil seco las coberturas quedan arriba de trigo y cebada, no en 6-8 puntos."""
        scores = self._batch(self._features(30.0, -50.0))
        self.assertLess(scores["trigo"], 45.0)  # la sequía sí castiga al trigo
        for cultivo in self.SIN_RINDE:
            self.assertGreater(scores[cultivo], scores["trigo"])
            self.assertGreater(scores[cultivo], scores["cebada"])
            self.assertGreater(scores[cultivo], 20.0)

    def test_coberturas_cerca_de_la_referencia_en_anio_normal(self) -> None:
        scores = self._batch(self._features(60.0, 0.0))
        referencia = (scores["trigo"] + scores["cebada"]) / 2
        for cultivo in self.SIN_RINDE:
            self.assertAlmostEqual(scores[cultivo], referencia, delta=5.0)
            self.assertLessEqual(abs(scores[cultivo] - 50.0), abs(referencia - 50.0) + 0.1)

    def test_ensemble_consistente_con_batch_en_coberturas(self) -> None:
        features = self._features(30.0, -50.0)
        actuales = {f: features[f] for f in CURRENT_FEATURES}
        esc = {f: features[f] for f in FUTURE_FEATURES}
        ens = self.predictor.predict_ensemble(actuales, [esc], "invierno", fecha_corte=date(2026, 5, 1), oni_actual=-1.0)
        batch = self._batch(features)
        self.assertEqual(set(ens), set(batch))
        for cultivo, score in batch.items():
            self.assertAlmostEqual(ens[cultivo]["promedio"], score, delta=0.11)

    def test_explicacion_menciona_demanda_hidrica_solo_con_perfil_seco(self) -> None:
        seco = run_recommendation(self._features(30.0, -50.0), campana="invierno", cultivo_anterior="soja_primera", fecha_ultimo_dato_valido="2026-04-15")
        normal = run_recommendation(self._features(60.0, 0.0), campana="invierno", cultivo_anterior="soja_primera", fecha_ultimo_dato_valido="2026-04-15")
        self.assertIn("los cultivos que más agua consumen", seco["recomendacion_principal"]["explicacion"])
        self.assertNotIn("los cultivos que más agua consumen", normal["recomendacion_principal"]["explicacion"])
        # 15/4: todas las coberturas todavía se pueden sembrar; con perfil seco no gana el trigo.
        self.assertNotEqual(seco["recomendacion_principal"]["cultivo"], "trigo")

    def test_nunca_recomienda_un_cultivo_fuera_de_ventana(self) -> None:
        """1/5: vicia y avena ya no se siembran; quedan al final y no son ni ganador ni alternativa."""
        resp = run_recommendation(self._features(30.0, -50.0), campana="invierno", cultivo_anterior="soja_primera", fecha_ultimo_dato_valido="2026-05-01")
        ranking = resp["ranking_cultivos"]
        fuera = [i["cultivo"] for i in ranking if i["fuera_de_ventana_siembra"]]
        self.assertEqual(set(fuera), {"vicia_cobertura", "avena_cobertura"})
        self.assertEqual([i["cultivo"] for i in ranking[-2:]], [c for c in [i["cultivo"] for i in ranking] if c in fuera])
        self.assertNotIn(resp["recomendacion_principal"]["cultivo"], fuera)
        explicacion = resp["recomendacion_principal"]["explicacion"]
        # El contraste "menor adaptación" tampoco puede ser un cultivo fuera de ventana.
        for cultivo in fuera:
            self.assertNotIn(f"{crop_with_article(cultivo)} (menor adaptación", explicacion.replace("A diferencia de la", "la"))
        self.assertNotIn("Vicia", explicacion.split(".")[0])
        self.assertNotIn("Avena", explicacion.split(".")[0])


class TestUmbralesRiesgoML8(unittest.TestCase):
    """ML-8: cortes de riesgo en la escala MAGyP (50 = año normal)."""

    def test_cortes_por_puntaje_hidroclimatico(self) -> None:
        esperado = {0.0: "critico", 39.9: "critico", 40.0: "alto", 44.9: "alto", 45.0: "medio",
                    49.9: "medio", 50.0: "bajo", 90.0: "bajo"}
        for hidro, nivel in esperado.items():
            self.assertEqual(classify_crop_risk(hidro, 80.0), nivel, hidro)

    def test_suelo_degradado_sube_a_alto_sin_bajar_critico(self) -> None:
        self.assertEqual(classify_crop_risk(60.0, 34.9), "alto")
        self.assertEqual(classify_crop_risk(47.0, 34.9), "alto")
        self.assertEqual(classify_crop_risk(30.0, 10.0), "critico")
        self.assertEqual(classify_crop_risk(60.0, 35.0), "bajo")

    def test_anio_normal_no_es_riesgo_alto(self) -> None:
        """Un cultivo en año normal, con suelo sano y P10 aceptable, no queda alto ni crítico."""
        self.assertEqual(escalate_risk_level(classify_crop_risk(52.0, 70.0), 35.0), "bajo")


class TestLoteOcupadoML11(unittest.TestCase):
    """ML-11: en verano, después de trigo, cebada o camelina, solo se recomiendan cultivos de segunda."""

    FEATURES = {
        "gwetroot_saturacion_pct": 44.0, "gwettop_saturacion_pct": 32.0,
        "tendencia_humedad_15d_pct": -1.0, "anomalia_lluvia_90d_pct": 20.0,
        "frecuencia_tormentas_extremas": 1.0, "frecuencia_estres_termico": 12.0,
        "frecuencia_riesgo_helada": 0.0, "indice_aridez_evaporativa": 1.2,
        "pendiente_terreno_pct": 0.2, "elevacion_m": 115.0, "textura_arcilla_pct": 24.5,
    }
    SEGUNDA = {"soja_segunda", "maiz_tardio", "sorgo"}

    def _resp(self, anterior: str | None, fecha: str = "2026-10-20") -> dict:
        return run_recommendation(self.FEATURES, campana="verano", cultivo_anterior=anterior, fecha_ultimo_dato_valido=fecha)

    def test_tras_trigo_solo_cultivos_de_segunda(self) -> None:
        for anterior in ("trigo", "cebada", "camelina"):
            resp = self._resp(anterior)
            ranking = resp["ranking_cultivos"]
            sembrables = [i["cultivo"] for i in ranking if i["motivo_no_sembrable"] is None]
            self.assertEqual(set(sembrables), self.SEGUNDA, anterior)
            self.assertEqual([i["cultivo"] for i in ranking[:3]], sembrables)
            self.assertIn(resp["recomendacion_principal"]["cultivo"], self.SEGUNDA)
            for item in ranking[3:]:
                self.assertIn("ocupado", item["motivo_no_sembrable"])
                self.assertFalse(item["fuera_de_ventana_siembra"])  # 20/10: la ventana sigue abierta
            primera_oracion = resp["recomendacion_principal"]["explicacion"].split(".")[0]
            for cultivo in ("Soja de Primera", "Girasol", "Maíz Temprano"):
                self.assertNotIn(cultivo, primera_oracion)
            testigo = resp["comparacion_estrategias"][0]
            self.assertEqual(testigo["cultivo_evaluado"], "soja_segunda")

    def test_coberturas_y_barbecho_no_restringen(self) -> None:
        for anterior in ("vicia_cobertura", "avena_cobertura", None, "soja_primera"):
            ranking = self._resp(anterior)["ranking_cultivos"]
            self.assertTrue(all(i["motivo_no_sembrable"] is None for i in ranking), anterior)

    def test_motivo_de_ventana_terminada(self) -> None:
        ranking = self._resp("vicia_cobertura", fecha="2026-11-15")["ranking_cultivos"]
        maiz = next(i for i in ranking if i["cultivo"] == "maiz_temprano")
        self.assertTrue(maiz["fuera_de_ventana_siembra"])
        self.assertIn("terminó el 31/10", maiz["motivo_no_sembrable"])
        self.assertEqual(ranking[-1]["cultivo"], "maiz_temprano")


class TestExplicacionML15(unittest.TestCase):
    """ML-15: escala en palabras, contraste con números, práctica habitual y cultivos no sembrables."""

    FEATURES = {
        "gwetroot_saturacion_pct": 46.0, "gwettop_saturacion_pct": 35.0,
        "tendencia_humedad_15d_pct": -4.0, "anomalia_lluvia_90d_pct": -38.6,
        "frecuencia_tormentas_extremas": 1.0, "frecuencia_estres_termico": 10.0,
        "frecuencia_riesgo_helada": 0.0, "indice_aridez_evaporativa": 0.8,
        "pendiente_terreno_pct": 1.0, "elevacion_m": 70.0, "textura_arcilla_pct": 25.0,
    }

    def test_tras_trigo(self) -> None:
        resp = run_recommendation(self.FEATURES, campana="verano", cultivo_anterior="trigo", fecha_ultimo_dato_valido="2026-11-12")
        rec = resp["recomendacion_principal"]
        texto = rec["explicacion"]
        # Sin porcentajes de aptitud de la escala FAO
        self.assertNotIn("% de aptitud", texto)
        self.assertNotIn("beneficio edáfico", texto)
        self.assertIn("donde 50 es un año normal", texto)
        self.assertIn("reserva hídrica ajustada", texto)
        # Cultivos no sembrables por el trigo, con nombre
        self.assertIn("no se pueden sembrar", texto)
        for nombre in ("Soja de Primera", "Girasol", "Maíz Temprano"):
            self.assertIn(nombre, texto.split("no se pueden sembrar")[1])
        self.assertIn("ocupado por el Trigo", texto)
        # Si el ganador es el testigo (doble cultivo), se dice
        if rec["cultivo"] == resp["comparacion_estrategias"][0]["cultivo_evaluado"]:
            self.assertIn("Coincide con la práctica habitual después del Trigo", texto)
        self.assertNotIn("menor adaptación al escenario actual", texto)
        self.assertNotIn("después de el ", texto)

    def test_helpers(self) -> None:
        from backend.ml.predictor import describir_reserva_hidrica, describir_rinde_esperado, enumerar

        self.assertEqual([describir_reserva_hidrica(g) for g in (35, 46, 60, 85)], ["baja", "ajustada", "adecuada", "alta"])
        self.assertEqual(describir_rinde_esperado(53.0), "levemente por encima de lo normal")
        self.assertEqual(describir_rinde_esperado(50.0), "en línea con un año normal")
        self.assertEqual(describir_rinde_esperado(40.0), "por debajo de lo normal")
        self.assertEqual(enumerar(["A", "B", "C"]), "A, B y C")


class TestDistribucionPredictivaML16(unittest.TestCase):
    """ML-16: probabilidad de año malo y rango real con el error fuera de muestra."""

    MAIZ_SOJA = ("maiz_temprano", "maiz_tardio", "soja_primera", "soja_segunda")

    @classmethod
    def setUpClass(cls) -> None:
        cls.predictor = get_predictor()
        cls.cal = cls.predictor.calibracion
        cls.current = {
            "gwetroot_saturacion_pct": 34.0, "gwettop_saturacion_pct": 28.5, "tendencia_humedad_15d_pct": -12.0,
            "anomalia_lluvia_90d_pct": -24.2, "indice_aridez_evaporativa": 0.52, "pendiente_terreno_pct": 1.8,
            "elevacion_m": 78.5, "textura_arcilla_pct": 24.5,
        }

    def _ens(self, campana: str = "verano", fecha: date = FECHA) -> dict[str, dict]:
        return self.predictor.predict_ensemble(self.current, ENSEMBLE_SCENARIOS, campana, fecha_corte=fecha)

    # --- funciones puras de ml/calibracion.py ---

    def test_resumen_ensemble_coincide_con_weighted_percentile(self) -> None:
        rng = np.random.default_rng(0)
        rid = np.repeat(np.arange(3), 7)
        pred = rng.uniform(20, 80, len(rid))
        peso = rng.choice([0.0, 1.0, 2.0], len(rid), p=[0.2, 0.5, 0.3])
        peso[::7] = 1.0  # cada fila con al menos un año análogo
        prom, p10 = calibracion.resumen_ensemble(rid, pred, peso, 3)
        for i in range(3):
            m = (rid == i) & (peso > 0)
            self.assertAlmostEqual(prom[i], float(np.average(pred[m], weights=peso[m])), places=9)
            self.assertAlmostEqual(p10[i], weighted_percentile(pred[m], 10.0, peso[m]), places=9)

    def test_prob_menor_es_monotona_y_acotada(self) -> None:
        grilla = calibracion.cuantiles_ponderados(np.linspace(-40, 30, 500), np.ones(500))
        x = np.linspace(-80, 80, 50)
        p = calibracion.prob_menor(grilla, x)
        self.assertTrue(np.all(np.diff(p) >= 0.0))
        self.assertGreater(p.min(), 0.0)
        self.assertLess(p.max(), 1.0)

    def test_tope_redondea_hacia_arriba_y_ignora_tramos_chicos(self) -> None:
        tramos = [
            {"frecuencia_real": 0.21, "fraccion_peso": 0.5},
            {"frecuencia_real": 0.33, "fraccion_peso": 0.3},
            {"frecuencia_real": 0.90, "fraccion_peso": 0.001},  # tramo casi vacío: no cuenta
        ]
        self.assertAlmostEqual(calibracion.tope_desde_diagrama(tramos), 0.35)

    def test_calibrar_da_cobertura_correcta_con_datos_sinteticos(self) -> None:
        """Con residuos iid, el año malo / año bueno dejan ~10% afuera de cada lado."""
        rng = np.random.default_rng(1)
        n = 6000
        df = pd.DataFrame({
            "anio_campana": rng.integers(2006, 2025, n),
            "cultivo_candidato": rng.choice(["trigo", "soja_primera"], n),
            "promedio": rng.uniform(40, 60, n),
            "p10": 0.0,
            "peso": 1.0,
        })
        df["puntaje_real"] = df["promedio"] + rng.normal(0, 20, n)
        cal = calibracion.calibrar(df)
        self.assertAlmostEqual(cal["metricas"]["cobertura_anio_malo"], 0.10, delta=0.02)
        self.assertAlmostEqual(cal["metricas"]["cobertura_anio_bueno"], 0.10, delta=0.02)
        self.assertEqual(set(cal["cuantiles_residuo"]), {"trigo", "soja_primera"})
        self.assertEqual(len(cal["cuantiles_residuo"]["trigo"]), len(calibracion.NIVELES))

    # --- bundle real ---

    def test_bundle_trae_calibracion_fuera_de_muestra(self) -> None:
        self.assertIsNotNone(self.cal)
        self.assertEqual(self.cal["version"], calibracion.VERSION_CALIBRACION)
        self.assertEqual(len(self.cal["campanas"]), 19)
        met = self.cal["metricas"]
        self.assertGreater(met["brier_skill"], 0.0)
        self.assertAlmostEqual(met["cobertura_anio_malo"], 0.10, delta=0.02)
        self.assertAlmostEqual(met["cobertura_anio_bueno"], 0.10, delta=0.02)
        self.assertEqual(set(self.cal["cuantiles_residuo"]), set(self.predictor.cultivos_entrenados))

    def test_probabilidad_solo_en_cultivos_que_anticipan(self) -> None:
        ens = self._ens("verano")
        for crop, d in ens.items():
            anticipa = self.cal["prob_valida_por_cultivo"][crop]
            self.assertEqual(d["anticipa_diferencias"], anticipa, crop)
            self.assertIsNotNone(d["prob_anio_malo_tipica"], crop)
            if anticipa:
                self.assertIsNotNone(d["prob_anio_malo"], crop)
                self.assertGreaterEqual(d["prob_anio_malo"], 0.0)
                self.assertLessEqual(d["prob_anio_malo"], self.cal["tope_prob"])
            else:
                self.assertIsNone(d["prob_anio_malo"], crop)
        # Con los datos actuales, maíz y soja anticipan; si cambia, revisar FRONT-36.
        for crop in self.MAIZ_SOJA:
            self.assertTrue(ens[crop]["anticipa_diferencias"], crop)

    def test_rango_real_es_mas_ancho_que_el_del_ensemble(self) -> None:
        """Si anticipa: alrededor del promedio y más ancho que el ensemble. Si no: el histórico."""
        for crop, d in self._ens("verano").items():
            if d["anticipa_diferencias"]:
                self.assertLess(d["puntaje_anio_malo"], d["promedio"] + penalizacion_demanda_hidrica(crop, 34.0) + 1e-6, crop)
                self.assertGreater(d["puntaje_anio_bueno"], d["promedio"], crop)
                self.assertLess(d["puntaje_anio_malo"], d["p10"], crop)
            else:
                g = self.cal["cuantiles_puntaje_real"][crop]
                self.assertAlmostEqual(d["puntaje_anio_malo"], calibracion.cuantil(g, 0.10), places=1)
                self.assertAlmostEqual(d["puntaje_anio_bueno"], calibracion.cuantil(g, 0.90), places=1)

    def test_cultivo_que_no_anticipa_usa_lo_normal(self) -> None:
        """Sin anticipación, el rinde esperado es el normal aunque el modelo diga otra cosa."""
        self.assertFalse(calibracion.anticipa(self.cal, "trigo"))
        self.assertEqual(calibracion.puntaje_esperado(self.cal, "trigo", 23.0), 50.0)
        self.assertTrue(calibracion.anticipa(self.cal, "soja_primera"))
        self.assertEqual(calibracion.puntaje_esperado(self.cal, "soja_primera", 23.0), 23.0)
        self.assertEqual(calibracion.puntaje_esperado(None, "trigo", 23.0), 23.0)

    def test_prob_baja_cuando_sube_el_promedio(self) -> None:
        crop = "soja_primera"
        probs = [calibracion.prob_anio_malo(self.cal, crop, x)["prob"] for x in (35.0, 45.0, 55.0, 65.0)]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertGreater(probs[0], probs[-1])

    def test_coberturas_sin_distribucion(self) -> None:
        ens = self._ens("invierno", date(2026, 5, 1))
        for crop in ("vicia_cobertura", "avena_cobertura", "camelina"):
            for campo in CAMPOS_DISTRIBUCION_PREDICTIVA:
                self.assertIsNone(ens[crop][campo], f"{crop}.{campo}")
        self.assertIsNotNone(ens["trigo"]["prob_anio_malo_tipica"])

    def test_bundle_sin_calibracion_deja_campos_en_none(self) -> None:
        original = self.predictor.calibracion
        try:
            self.predictor.calibracion = None
            for d in self._ens("verano").values():
                for campo in CAMPOS_DISTRIBUCION_PREDICTIVA:
                    self.assertIsNone(d[campo])
        finally:
            self.predictor.calibracion = original

    def test_ranking_publico_trae_los_campos(self) -> None:
        out = run_recommendation(
            features={**self.current, "frecuencia_tormentas_extremas": 1.0, "frecuencia_estres_termico": 6.0,
                      "frecuencia_riesgo_helada": 0.0},
            campana="verano", cultivo_anterior="soja_primera", objetivo_productor="equilibrio",
            escenarios_historicos=ENSEMBLE_SCENARIOS,
        )
        for item in out["ranking_cultivos"]:
            for campo in CAMPOS_DISTRIBUCION_PREDICTIVA:
                self.assertIn(campo, item)
        dist = out["recomendacion_principal"]["distribucion_hidroclimatica"]
        self.assertIn("prob_anio_malo_tipica", dist)


class TestRindeKgHaML17(unittest.TestCase):
    """ML-17: rinde en kg/ha con la tendencia MAGyP del departamento más cercano."""

    PERGAMINO = {"lat": -33.95, "lon": -60.57}
    MENDOZA = {"lat": -32.89, "lon": -68.83}
    CURRENT = {
        "gwetroot_saturacion_pct": 46.0, "gwettop_saturacion_pct": 40.0, "tendencia_humedad_15d_pct": -3.0,
        "anomalia_lluvia_90d_pct": -10.0, "indice_aridez_evaporativa": 0.6, "pendiente_terreno_pct": 0.8,
        "elevacion_m": 80.0, "textura_arcilla_pct": 25.0,
    }

    def _rec(self, campana: str = "verano", fecha: date = date(2026, 11, 15), **kwargs) -> dict:
        return run_recommendation(
            self.CURRENT, campana=campana, cultivo_anterior="soja_primera",
            escenarios_historicos=ENSEMBLE_SCENARIOS, fecha_corte=fecha, **kwargs,
        )

    def test_conversion_invierte_el_label(self) -> None:
        self.assertAlmostEqual(rinde.rinde_desde_puntaje(50.0, 3000.0), 3000.0)
        self.assertAlmostEqual(rinde.rinde_desde_puntaje(30.0, 3000.0), 2400.0)
        self.assertAlmostEqual(rinde.rinde_desde_puntaje(70.0, 3000.0), 3600.0)
        self.assertEqual(rinde.rinde_desde_puntaje(-80.0, 3000.0), 0.0)

    def test_redondeo_a_50_kg(self) -> None:
        r = rinde.rinde_kg_ha("soja_primera", "06623", "Pergamino", 2026, 51.3, 20.1, 79.9)
        for k in ("esperado", "anio_malo", "anio_bueno", "normal"):
            self.assertEqual(r[k] % 50, 0, k)
        self.assertLess(r["anio_malo"], r["esperado"])
        self.assertLess(r["esperado"], r["anio_bueno"])

    def test_departamento_mas_cercano(self) -> None:
        dep = departamentos.departamento_mas_cercano(**self.PERGAMINO)
        self.assertEqual(dep["nombre"], "Pergamino")
        self.assertLess(dep["distancia_km"], departamentos.DISTANCIA_MAXIMA_KM)
        self.assertIsNone(departamentos.departamento_mas_cercano(**self.MENDOZA))
        self.assertEqual(departamentos.departamento_por_codigo(dep["codigo"])["nombre"], "Pergamino")

    def test_respuesta_con_rinde_y_departamento(self) -> None:
        out = self._rec(ubicacion=self.PERGAMINO)
        self.assertEqual(out["departamento_referencia"]["nombre"], "Pergamino")
        por_cultivo = {i["cultivo"]: i["rinde_kg_ha"] for i in out["ranking_cultivos"]}
        for crop, r in por_cultivo.items():
            self.assertIsNotNone(r["normal"], crop)
            self.assertLess(r["anio_malo"], r["anio_bueno"], crop)
        # Los dos maíces comparten el rinde "maíz" de MAGyP.
        self.assertEqual(por_cultivo["maiz_temprano"]["normal"], por_cultivo["maiz_tardio"]["normal"])
        ganador = out["recomendacion_principal"]
        self.assertEqual(ganador["rinde_kg_ha"], por_cultivo[ganador["cultivo"]])

    def test_fuera_de_cobertura(self) -> None:
        out = self._rec(ubicacion=self.MENDOZA)
        self.assertIsNone(out["departamento_referencia"])
        for item in out["ranking_cultivos"]:
            self.assertIsNone(item["rinde_kg_ha"]["esperado"])
            self.assertEqual(item["rinde_kg_ha"]["motivo_sin_dato"], rinde.MOTIVO_FUERA_DE_COBERTURA)

    def test_coberturas_sin_rinde(self) -> None:
        out = self._rec("invierno", date(2026, 5, 1), ubicacion=self.PERGAMINO)
        por_cultivo = {i["cultivo"]: i["rinde_kg_ha"] for i in out["ranking_cultivos"]}
        for crop in ("vicia_cobertura", "avena_cobertura", "camelina"):
            self.assertIsNone(por_cultivo[crop]["esperado"])
            self.assertEqual(por_cultivo[crop]["motivo_sin_dato"], rinde.MOTIVO_SIN_MAGYP)
        self.assertIsNotNone(por_cultivo["trigo"]["normal"])

    def test_departamento_guardado_tiene_prioridad(self) -> None:
        otro = departamentos.departamento_mas_cercano(-31.4, -64.2)  # Córdoba
        out = self._rec(ubicacion=self.PERGAMINO, departamento_codigo=otro["codigo"])
        self.assertEqual(out["departamento_referencia"]["codigo"], otro["codigo"])
        self.assertGreater(out["departamento_referencia"]["distancia_km"], 200.0)  # distancia real del lote


if __name__ == "__main__":
    unittest.main()


class TestSeguimientoML18(unittest.TestCase):
    """ML-18: seguimiento en campaña con ventana mezclada (observado + años análogos)."""

    CULTIVO = "soja_primera"
    SIEMBRA = date(2026, 11, 10)

    @classmethod
    def setUpClass(cls) -> None:
        from backend.providers.features import codificar_lluvia

        cls.predictor = get_predictor()
        rng = np.random.default_rng(7)

        def anio(a: int, calor: float) -> tuple[str, str]:
            n = 366 if a % 4 == 0 else 365
            ev = "".join(rng.choice(["0", "2"], p=[1 - calor, calor]) for _ in range(n))
            ll = "".join(codificar_lluvia(float(x)) for x in rng.gamma(0.6, 5.0, n))
            return ev, ll

        cls.hist_ev, cls.hist_ll = {}, {}
        for a in range(1981, 2026):
            cls.hist_ev[a], cls.hist_ll[a] = anio(a, 0.10)
        # La campaña actual: un verano muy caluroso (para que la probabilidad suba al observarlo).
        cls.obs_ev, cls.obs_ll = dict(cls.hist_ev), dict(cls.hist_ll)
        for a in (2026, 2027):
            cls.obs_ev[a], cls.obs_ll[a] = anio(a, 0.55)
        cls.actuales = {
            "gwetroot_saturacion_pct": 46.0, "gwettop_saturacion_pct": 40.0, "tendencia_humedad_15d_pct": -3.0,
            "anomalia_lluvia_90d_pct": -10.0, "indice_aridez_evaporativa": 0.6, "pendiente_terreno_pct": 0.8,
            "elevacion_m": 80.0, "textura_arcilla_pct": 25.0, "oni_actual": 0.1,
        }
        cls.inicio = escenarios.inicio_periodo_critico_real(cls.CULTIVO, cls.SIEMBRA)

    def _seg(self, ultimo: date, **kw) -> dict:
        return self.predictor.predict_seguimiento(
            self.actuales, self.hist_ev, self.hist_ll, self.obs_ev, self.obs_ll,
            self.CULTIVO, self.SIEMBRA, ultimo, departamento=departamentos.departamento_mas_cercano(-33.95, -60.57), **kw,
        )

    def test_dias_observados_acotados(self) -> None:
        i = self.inicio
        self.assertEqual(escenarios.dias_observados(i, i - timedelta(days=10)), 0)
        self.assertEqual(escenarios.dias_observados(i, i), 1)
        self.assertEqual(escenarios.dias_observados(i, i + timedelta(days=200)), 90)

    def test_sin_dias_observados_coincide_con_los_analogos(self) -> None:
        lista, d = escenarios.escenarios_en_curso(
            self.hist_ev, self.hist_ll, self.obs_ev, self.obs_ll, self.CULTIVO, self.SIEMBRA,
            self.inicio - timedelta(days=1), 0.1,
        )
        self.assertEqual(d, 0)
        for e in lista:
            ref = features_ventana(self.hist_ev, self.hist_ll, escenarios.fecha_equivalente(self.inicio, 2026, e["anio"]), 90)
            self.assertEqual({k: e[k] for k in ref}, ref)

    def test_todo_observado_da_la_misma_ventana_en_todos_los_anios(self) -> None:
        lista, d = escenarios.escenarios_en_curso(
            self.hist_ev, self.hist_ll, self.obs_ev, self.obs_ll, self.CULTIVO, self.SIEMBRA,
            self.inicio + timedelta(days=120), 0.1,
        )
        self.assertEqual(d, 90)
        observado = features_ventana(self.obs_ev, self.obs_ll, self.inicio, 90)
        for e in lista:
            self.assertEqual({k: e[k] for k in observado}, observado)

    def test_etapas_y_serie(self) -> None:
        previa = self._seg(self.inicio - timedelta(days=5))
        self.assertEqual(previa["etapa"], "previa")
        self.assertEqual(len(previa["serie"]), 1)
        self.assertEqual(previa["serie"][0]["dias_observados"], 0)
        self.assertIsNone(previa["observado"])

        curso = self._seg(self.inicio + timedelta(days=30))
        self.assertEqual(curso["etapa"], "en_curso")
        self.assertEqual(curso["dias_observados"], 31)
        dias = [p["dias_observados"] for p in curso["serie"]]
        self.assertEqual(dias[0], 0)
        self.assertEqual(dias[-1], 31)
        self.assertEqual(dias, sorted(dias))
        self.assertEqual(curso["observado"]["dias"], 31)
        self.assertGreater(curso["observado"]["dias_calor"], 5)

        fin = self._seg(self.inicio + timedelta(days=150))
        self.assertEqual(fin["etapa"], "terminado")
        self.assertEqual(fin["serie"][-1]["dias_observados"], 90)

    def test_un_verano_muy_caluroso_sube_la_probabilidad(self) -> None:
        fin = self._seg(self.inicio + timedelta(days=150))
        primero, ultimo = fin["serie"][0], fin["serie"][-1]
        self.assertLess(ultimo["promedio"], primero["promedio"])
        if primero["prob_anio_malo"] is not None and ultimo["prob_anio_malo"] is not None:
            self.assertGreaterEqual(ultimo["prob_anio_malo"], primero["prob_anio_malo"])
        self.assertIsNotNone(ultimo["rinde_kg_ha"]["normal"])

    def test_bundle_con_grillas_por_avance_que_mejoran(self) -> None:
        seg = self.predictor.seguimiento
        self.assertIsNotNone(seg)
        self.assertEqual(seg["niveles"], ["0.00", "0.25", "0.50", "0.75", "1.00"])
        self.assertTrue(seg["criterio_brier_final_menor_que_inicial"])
        res = seg["resumen"]
        self.assertGreater(res["1.00"]["brier_skill"], res["0.00"]["brier_skill"])
        self.assertLessEqual(res["1.00"]["ancho_rango_medio"], res["0.00"]["ancho_rango_medio"])
        self.assertTrue(self._seg(self.inicio + timedelta(days=30))["rango_por_avance"])

    def test_cobertura_no_tiene_seguimiento(self) -> None:
        with self.assertRaises(ValueError):
            self.predictor.predict_seguimiento(
                self.actuales, self.hist_ev, self.hist_ll, self.obs_ev, self.obs_ll,
                "vicia_cobertura", date(2026, 3, 10), date(2026, 5, 1),
            )
