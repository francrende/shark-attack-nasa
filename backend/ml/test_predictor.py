"""Suite de pruebas unitarias e integración para ML-4 (``backend/ml/predictor.py``)."""

from __future__ import annotations

import time
import unittest

import numpy as np

from backend.ml.predictor import (
    AgroPredictor,
    apply_what_if_simulation,
    classify_crop_risk,
    compute_hybrid_final_score,
    detect_physical_anomalies,
    get_predictor,
    run_recommendation,
)


class TestAgroPredictorML4(unittest.TestCase):
    """Verifica inferencia online, MCDA, anomalías, What-If y contrato JSON de CONTEXT.md."""

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
        self.assertEqual(len(self.predictor.feature_columns), 12)
        self.assertEqual(len(self.predictor.crops_catalog["by_name"]), 11)

    def test_02_context_md_benchmark_contract_and_ranking(self) -> None:
        """Verifica que el caso testigo de CONTEXT.md Sección 5 reproduzca ranking, riesgos y estructura."""
        resp = run_recommendation(
            features=self.context_drought_features,
            campana="verano",
            cultivo_anterior="soja_primera",
            objetivo_productor="equilibrio",
            carbono_organico_g_kg=18.4,
            ubicacion={"lat": -33.95, "lon": -60.57},
        )

        # Bloques obligatorios de CONTEXT.md Sección 5
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

        # Recomendación principal debe ser sorgo con s_suelo = 95.0
        rec = resp["recomendacion_principal"]
        self.assertEqual(rec["cultivo"], "sorgo")
        self.assertEqual(rec["sub_scores"]["suelo"], 95.0)
        self.assertGreaterEqual(rec["score_final"], 88.0)
        self.assertEqual(len(rec["factores_clave_ml"]), 3)
        self.assertIn("Recomendación: Sembrar Sorgo", rec["explicacion"])

        # Verificar orden y niveles de riesgo bidimensionales del ranking
        ranking = resp["ranking_cultivos"]
        by_crop = {item["cultivo"]: item for item in ranking}
        self.assertEqual(ranking[0]["cultivo"], "sorgo")
        self.assertEqual(ranking[1]["cultivo"], "maiz_tardio")
        self.assertEqual(ranking[-1]["cultivo"], "soja_primera")

        # Etiquetas de riesgo idénticas a CONTEXT.md Sección 5
        self.assertEqual(by_crop["sorgo"]["riesgo"], "bajo")
        self.assertEqual(by_crop["maiz_tardio"]["riesgo"], "medio")
        self.assertEqual(by_crop["girasol"]["riesgo"], "bajo")
        self.assertEqual(by_crop["maiz_temprano"]["riesgo"], "critico")
        self.assertEqual(by_crop["soja_primera"]["riesgo"], "alto")

        # Penalización Opción B lleva soja_primera a ~31 pts (31.2 vs 31.0 de CONTEXT.md)
        self.assertAlmostEqual(by_crop["soja_primera"]["score_final"], 31.2, delta=2.0)

    def test_03_what_if_internal_coupling_and_independent_controls(self) -> None:
        """Verifica que los sliders What-If sean independientes pero mantengan consistencia física."""
        # A) Solo variación de lluvia (+30%) -> actualiza anomalía, índice de aridez y humedad acoplada
        sim_rain = apply_what_if_simulation(
            self.context_drought_features,
            override_humedad_radicular_pct=None,
            variacion_lluvia_esperada_pct=30.0,
        )
        self.assertAlmostEqual(sim_rain["anomalia_lluvia_90d_pct"], 5.8, places=1)
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
        self.assertGreater(maiz_wet - maiz_drought, 18.0)

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
        waterlog_feat["frecuencia_estres_termico"] = 13.0
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


if __name__ == "__main__":
    unittest.main()
