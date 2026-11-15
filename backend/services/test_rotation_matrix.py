"""Tests unitarios para la Matriz de Rotación Agronómica (ML-3)."""

from __future__ import annotations

import unittest

from backend.ml.generate_dataset import CROP_CATALOG
from backend.services.rotation_matrix import (
    ALL_CROPS,
    CROP_PROFILES,
    INVIERNO_CROPS,
    VERANO_CROPS,
    compare_rotation_strategies,
    evaluate_campaign_soil,
    evaluate_soil_and_rotation,
    get_crop_numeric_id,
    get_crops_for_campaign,
    penalizacion_demanda_hidrica,
)


class TestRotationMatrix(unittest.TestCase):
    def test_catalog_matches_ml1_dataset_ids_and_campaigns(self) -> None:
        self.assertEqual(len(INVIERNO_CROPS), 5)
        self.assertEqual(len(VERANO_CROPS), 6)
        self.assertEqual(len(ALL_CROPS), 11)
        self.assertEqual(get_crops_for_campaign("invierno"), INVIERNO_CROPS)
        self.assertEqual(get_crops_for_campaign("verano"), VERANO_CROPS)

        # Verifica sincronización 1:1 con CROP_CATALOG de ML-1 (generate_dataset.py)
        self.assertEqual(set(CROP_PROFILES.keys()), set(CROP_CATALOG.keys()))
        for crop_id, ml1_spec in CROP_CATALOG.items():
            profile = CROP_PROFILES[crop_id]
            self.assertEqual(profile.numeric_id, ml1_spec["id"])
            self.assertEqual(get_crop_numeric_id(crop_id), ml1_spec["id"])
            self.assertEqual(profile.campana, ml1_spec["campana"])

    def test_all_scores_stay_within_0_100_even_under_extremes(self) -> None:
        for prev in [None, "ninguno", "barbecho", *ALL_CROPS]:
            for cand in ALL_CROPS:
                for soc in [None, 5.0, 18.0, 35.0]:
                    for slope in [None, 0.2, 1.8, 5.0]:
                        for clay in [None, 12.0, 24.5, 38.0]:
                            res = evaluate_soil_and_rotation(
                                cultivo_candidato=cand,
                                cultivo_anterior=prev,
                                carbono_organico_g_kg=soc,
                                pendiente_terreno_pct=slope,
                                arcilla_pct=clay,
                                phh2o=6.2,
                            )
                            self.assertGreaterEqual(res.s_suelo, 0.0)
                            self.assertLessEqual(res.s_suelo, 100.0)
                            self.assertEqual(len(res.calendario_12m), 12)
                            self.assertGreaterEqual(res.meses_suelo_desnudo, 0)
                            self.assertLessEqual(res.meses_suelo_desnudo, 12)

    def test_context_md_reference_case_calibration(self) -> None:
        # Caso oficial de CONTEXT.md Sección 5:
        # cultivo_anterior="soja_primera", soc=18.4, pendiente=1.8, arcilla=24.5
        sorgo = evaluate_soil_and_rotation(
            cultivo_candidato="sorgo",
            cultivo_anterior="soja_primera",
            carbono_organico_g_kg=18.4,
            pendiente_terreno_pct=1.8,
            arcilla_pct=24.5,
        )
        soja_repeat = evaluate_soil_and_rotation(
            cultivo_candidato="soja_primera",
            cultivo_anterior="soja_primera",
            carbono_organico_g_kg=18.4,
            pendiente_terreno_pct=1.8,
            arcilla_pct=24.5,
        )
        self.assertEqual(sorgo.s_suelo, 95.0)
        self.assertEqual(sorgo.condicion_rotacion_previa, "deficit_rastrojo_por_soja")
        self.assertEqual(
            sorgo.secuencia_sugerida,
            "vicia_cobertura (invierno) -> sorgo / maiz_tardio (verano)",
        )
        self.assertEqual(soja_repeat.s_suelo, 15.0)

    def test_soja_segunda_penalized_after_summer_crop_vs_soja_primera(self) -> None:
        after_maiz_soja1 = evaluate_soil_and_rotation(
            cultivo_candidato="soja_primera",
            cultivo_anterior="maiz_tardio",
            carbono_organico_g_kg=20.0,
            pendiente_terreno_pct=0.8,
        )
        after_maiz_soja2 = evaluate_soil_and_rotation(
            cultivo_candidato="soja_segunda",
            cultivo_anterior="maiz_tardio",
            carbono_organico_g_kg=20.0,
            pendiente_terreno_pct=0.8,
        )
        after_trigo_soja2 = evaluate_soil_and_rotation(
            cultivo_candidato="soja_segunda",
            cultivo_anterior="trigo",
            carbono_organico_g_kg=20.0,
            pendiente_terreno_pct=0.8,
        )
        self.assertGreater(after_maiz_soja1.s_suelo, after_maiz_soja2.s_suelo + 20.0)
        self.assertGreater(after_trigo_soja2.s_suelo, after_maiz_soja2.s_suelo + 30.0)

    def test_double_crop_calendar_distinguishes_previous_and_candidate(self) -> None:
        doble_cultivo = evaluate_soil_and_rotation(
            cultivo_candidato="soja_segunda",
            cultivo_anterior="trigo",
            carbono_organico_g_kg=20.0,
            pendiente_terreno_pct=0.8,
        )
        estados = {m.estado for m in doble_cultivo.calendario_12m}
        self.assertIn("cultivo_candidato", estados)
        self.assertIn("cultivo_antecesor", estados)
        self.assertLessEqual(doble_cultivo.meses_suelo_desnudo, 1)

    def test_texture_adjustment_on_sandy_and_heavy_clay_soils(self) -> None:
        sorgo_sandy = evaluate_soil_and_rotation(
            cultivo_candidato="sorgo",
            cultivo_anterior="soja_primera",
            arcilla_pct=14.0,
        )
        soja_sandy = evaluate_soil_and_rotation(
            cultivo_candidato="soja_primera",
            cultivo_anterior="maiz_tardio",
            arcilla_pct=14.0,
        )
        self.assertEqual(sorgo_sandy.ajuste_textura, 5.0)
        self.assertEqual(soja_sandy.ajuste_textura, -6.0)

    def test_compare_rotation_strategies_returns_three_distinct_strategies(self) -> None:
        strategies = compare_rotation_strategies(
            campana="verano",
            cultivo_anterior="soja_primera",
            carbono_organico_g_kg=18.4,
            pendiente_terreno_pct=1.8,
        )
        self.assertEqual(len(strategies), 3)
        testigo, defensiva, regenerativa = strategies
        self.assertLess(testigo.s_suelo, defensiva.s_suelo)
        self.assertLess(testigo.s_suelo, regenerativa.s_suelo)
        self.assertGreater(defensiva.reduccion_suelo_desnudo_vs_testigo, 0)

    def test_penalizacion_demanda_hidrica(self) -> None:
        """ML-10: sin penalización con perfil cargado; con perfil seco pesa más el que más consume."""
        for cultivo in ALL_CROPS:
            self.assertEqual(penalizacion_demanda_hidrica(cultivo, 45.0), 0.0)
            self.assertEqual(penalizacion_demanda_hidrica(cultivo, 80.0), 0.0)
            self.assertLessEqual(penalizacion_demanda_hidrica(cultivo, 0.0), 10.0)
        self.assertEqual(penalizacion_demanda_hidrica("maiz_temprano", 25.0), 10.0)
        self.assertGreater(
            penalizacion_demanda_hidrica("trigo", 30.0), penalizacion_demanda_hidrica("vicia_cobertura", 30.0)
        )
        self.assertGreater(
            penalizacion_demanda_hidrica("trigo", 25.0), penalizacion_demanda_hidrica("trigo", 35.0)
        )


if __name__ == "__main__":
    unittest.main()
