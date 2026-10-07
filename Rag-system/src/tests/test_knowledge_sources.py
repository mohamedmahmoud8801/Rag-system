from models.db_schemes.ragsystem.schemes.datachunk import RetrievedDocument
from controllers.KnowledgeController import KnowledgeController


def test_build_sources_from_retrieved_documents():

    documents = [
        RetrievedDocument(
            text="Attention is a mechanism.",
            score=0.91,
            chunk_id=75,
            metadata={
                "source": "attention.pdf",
                "page": 3,
            },
        ),
        RetrievedDocument(
            text="Self-attention uses Q, K and V.",
            score=0.87,
            chunk_id=76,
            metadata={
                "source": "attention.pdf",
                "page": 4,
            },
        ),
    ]

    sources = KnowledgeController._build_sources(
        documents
    )

    assert len(sources) == 2

    assert sources[0] == {
        "chunk_id": 75,
        "source": "attention.pdf",
        "page": 3,
        "score": 0.91,
    }

    assert sources[1] == {
        "chunk_id": 76,
        "source": "attention.pdf",
        "page": 4,
        "score": 0.87,
    }


def test_build_sources_handles_missing_metadata():

    documents = [
        RetrievedDocument(
            text="Some content.",
            score=0.75,
            chunk_id=100,
            metadata=None,
        )
    ]

    sources = KnowledgeController._build_sources(
        documents
    )

    assert sources == [
        {
            "chunk_id": 100,
            "source": None,
            "page": None,
            "score": 0.75,
        }
    ]


def test_attach_sources_preserves_existing_result():

    documents = [
        RetrievedDocument(
            text="Attention content.",
            score=0.88,
            chunk_id=55,
            metadata={
                "source": "transformer.pdf",
                "page": 7,
            },
        )
    ]

    result = {
        "answer": "Attention is a mechanism.",
        "documents": documents,
        "query": "What is attention?",
    }

    updated = KnowledgeController._attach_sources(
        result
    )

    assert updated["answer"] == "Attention is a mechanism."
    assert updated["query"] == "What is attention?"
    assert updated["documents"] == documents

    assert updated["sources"] == [
        {
            "chunk_id": 55,
            "source": "transformer.pdf",
            "page": 7,
            "score": 0.88,
        }
    ]


def test_attach_sources_handles_empty_documents():

    result = {
        "answer": None,
        "documents": [],
    }

    updated = KnowledgeController._attach_sources(
        result
    )

    assert updated["sources"] == []


def test_build_sources_handles_partial_metadata():

    documents = [
        RetrievedDocument(
            text="Content.",
            score=0.81,
            chunk_id=42,
            metadata={
                "source": "lecture.pdf",
            },
        )
    ]

    sources = KnowledgeController._build_sources(
        documents
    )

    assert sources == [
        {
            "chunk_id": 42,
            "source": "lecture.pdf",
            "page": None,
            "score": 0.81,
        }
    ]
