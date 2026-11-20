"""Los registros son sintéticos; estas pruebas verifican cálculo, no calidad RAG."""
from copy import deepcopy

import pytest
from herramientas.evaluar_matriz_rag import evaluar, evaluar_registro


def registro(case="RAG-001"):
    return dict(caseId=case, evaluatedAt="2026-11-19T12:00:00Z", commit="a" * 40,
        indexedDocumentIds=["doc"], models={"retrieval": "simulado", "generation": "simulado"},
        query="Consulta sintética", executionKind="live", dataKind="synthetic",
        annotationStatus="reviewed_independently", topK=5,
        results=[dict(chunkId=f"c{i}", documentId="doc", score=0.9-i/10,
                      relevant=i == 3, judgedBy="evaluador") for i in range(1, 6)],
        groundTruth=dict(relevantDocumentIds=["doc"], expectedDocumentId="doc", complete=True),
        rag=dict(outcome="draft", content="Procedimiento [c3]", sourceChunkIds=["c3"], sourcesVisible=True,
                 fallbackAppropriate=None, citations=[dict(chunkId="c3", supportsClaim=True, reviewedBy="revisor")]),
        humanReviews=[dict(reviewer="persona-a", rating=3), dict(reviewer="persona-b", rating=5)],
        observations="Datos de prueba, no evidencia operativa.")


def test_precision_rr_recall_y_score_con_un_acierto_en_tercera_posicion():
    result = evaluar_registro(registro())
    assert result["verdict"] == "apto"
    assert result["metrics"] == dict(precisionAt3=1/3, precisionAt5=1/5, recallAt5=1,
        reciprocalRank=1/3, meanRelevantScore=pytest.approx(0.6), fallbackCorrect=None,
        citationAccuracy=1, citationTraceability=1, meanHumanRelevance=4)


def test_sin_juicio_anterior_al_acierto_no_inventa_rango_o_precision():
    record = registro()
    record["results"][0]["relevant"] = None
    result = evaluar_registro(record)
    assert result["metrics"]["reciprocalRank"] is None
    assert result["metrics"]["precisionAt3"] is None
    assert result["verdict"] == "pendiente"


@pytest.mark.parametrize("case", ["RAG-001", "RAG-002", "RAG-003", "RAG-005"])
def test_criterios_positivos(case):
    assert evaluar_registro(registro(case))["criterionMet"] is True


def test_rango_cuatro_no_cumple_001_ni_002():
    for case in ("RAG-001", "RAG-002"):
        record = registro(case)
        for i, result in enumerate(record["results"], 1): result["relevant"] = i == 4
        assert evaluar_registro(record)["verdict"] == "no_apto"


def test_recall_sin_catalogo_completo_y_juicio_humano_pendiente():
    record = registro("RAG-003")
    record["groundTruth"]["complete"] = False
    assert evaluar_registro(record)["verdict"] == "pendiente"
    record = registro("RAG-005")
    record["humanReviews"] = []
    assert evaluar_registro(record)["verdict"] == "pendiente"
    record["humanReviews"] = [dict(reviewer="persona", rating=3.9)]
    assert evaluar_registro(record)["verdict"] == "no_apto"


@pytest.mark.parametrize("alter", ["fuente_inventada", "cita_inventada", "cita_inexacta", "fuente_invisible"])
def test_fuentes_y_citas_son_condicion_de_aptitud(alter):
    record = registro()
    if alter == "fuente_inventada": record["rag"]["sourceChunkIds"].append("inventada")
    if alter == "cita_inventada": record["rag"]["citations"][0]["chunkId"] = "inventada"
    if alter == "cita_inexacta": record["rag"]["citations"][0]["supportsClaim"] = False
    if alter == "fuente_invisible": record["rag"]["sourcesVisible"] = False
    assert evaluar_registro(record)["verdict"] == "no_apto"


def fallback():
    record = registro("RAG-004")
    record["rag"].update(outcome="fallback", content="Sin evidencia suficiente", sourceChunkIds=[],
                         citations=[], fallbackAppropriate=True)
    return record


def test_fallback_correcto_no_admite_fuentes_ni_citas():
    record = fallback()
    assert evaluar_registro(record)["verdict"] == "apto"
    record["rag"]["sourceChunkIds"] = ["inventada"]
    assert evaluar_registro(record)["verdict"] == "no_apto"


def test_suite_completa_no_es_aprobacion_productiva_y_preserva_registro():
    records = [registro(f"RAG-{i:03}") if i != 4 else fallback() for i in range(1, 6)]
    before = deepcopy(records)
    report = evaluar(records)
    assert report["verdict"] == "apto" and report["productionApproved"] is False
    assert report["mrr"] == pytest.approx(1/3) and report["fallbackCorrectRate"] == 1
    assert [case["record"] for case in report["cases"]] == before == records
    records[0]["executionKind"] = "fixture"
    assert evaluar(records)["verdict"] == "pendiente"
    assert evaluar(records[1:])["missingCases"] == ["RAG-001"]


@pytest.mark.parametrize("alter", ["nan", "repetido", "fecha", "commit", "revisor"])
def test_datos_invalidos_rechazados(alter):
    record = registro()
    if alter == "nan": record["results"][0]["score"] = float("nan")
    if alter == "repetido": record["results"][1]["chunkId"] = "c1"
    if alter == "fecha": record["evaluatedAt"] = "2026-11-19"
    if alter == "commit": record["commit"] = "desconocido"
    if alter == "revisor": record["rag"]["citations"][0]["reviewedBy"] = ""
    with pytest.raises(ValueError): evaluar_registro(record)


def test_cli_conserva_evidencia_y_no_imprime_consultas_o_sobrescribe(tmp_path, monkeypatch, capsys):
    import json
    import sys
    from herramientas import evaluar_matriz_rag as modulo
    monkeypatch.setattr(modulo, "RAIZ", tmp_path)
    source = tmp_path / "entrada.json"
    destination = tmp_path / "artifacts" / "informe.json"
    record = registro()
    record["executionKind"] = "fixture"
    source.write_text(json.dumps({"records": [record]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["evaluar", "--records", str(source), "--output", str(destination)])
    modulo.main()
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert report["verdict"] == "pendiente" and report["cases"][0]["record"] == record
    assert "Consulta" not in capsys.readouterr().out
    previous = destination.read_bytes()
    with pytest.raises(SystemExit) as error: modulo.main()
    assert error.value.code == 1 and destination.read_bytes() == previous


def test_cli_rechaza_destino_publicable(tmp_path, monkeypatch):
    import sys
    from herramientas import evaluar_matriz_rag as modulo
    monkeypatch.setattr(modulo, "RAIZ", tmp_path)
    destination = tmp_path / "docs" / "informe.json"
    monkeypatch.setattr(sys, "argv", ["evaluar", "--records", "no-leer.json", "--output", str(destination)])
    with pytest.raises(SystemExit) as error: modulo.main()
    assert error.value.code == 1 and not destination.exists()
