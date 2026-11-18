import unittest
import base64
import json
import re

from src.api_doc_sync.model import (
    CanonicalApiModel,
    HeaderFact,
    NOT_FOUND,
    OperationFact,
    ParameterFact,
    PathFact,
    RequestBodyFact,
    ResponseFact,
    SchemaFact,
    deserialize_metadata,
    serialize_metadata,
)


class CanonicalApiModelTests(unittest.TestCase):
    def test_missing_values_use_not_found(self):
        operation = OperationFact()

        self.assertEqual(operation.path, NOT_FOUND)
        self.assertEqual(operation.method, NOT_FOUND)
        self.assertEqual(operation.summary, NOT_FOUND)

        parameter = ParameterFact()
        self.assertEqual(parameter.name, NOT_FOUND)
        self.assertEqual(parameter.location, NOT_FOUND)
        self.assertEqual(parameter.schema, {"type": NOT_FOUND})

    def test_structured_model_round_trip(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            paths=(PathFact(path="/pets", summary="Pet operations"),),
            operations=(
                OperationFact(
                    path="/pets",
                    method="get",
                    summary="List pets",
                    parameters=(
                        ParameterFact(
                            name="limit",
                            location="query",
                            required=False,
                            schema={"type": "integer"},
                        ),
                        ParameterFact(
                            name="Authorization",
                            location="header",
                            required=True,
                            schema={"type": "string"},
                        ),
                    ),
                    request_body=RequestBodyFact(
                        required=True,
                        schemas=(
                            SchemaFact(
                                name="CreatePet",
                                media_type="application/json",
                                schema={
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                },
                            ),
                        ),
                    ),
                    responses=(
                        ResponseFact(
                            status="200",
                            description=NOT_FOUND,
                            headers=(
                                HeaderFact(
                                    name="X-Rate-Limit",
                                    required=False,
                                    schema={"type": "integer"},
                                ),
                            ),
                            schemas=(
                                SchemaFact(
                                    name="Pet",
                                    media_type="application/json",
                                    schema={"type": "object"},
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            schemas=(
                SchemaFact(
                    name="Pet",
                    schema={"type": "object", "properties": {}},
                ),
            ),
        )

        restored = CanonicalApiModel.from_dict(model.to_dict())

        self.assertEqual(restored, model.normalized())
        self.assertEqual(restored.openapi_version, "3.1.0")
        self.assertEqual(restored.operations[0].method, "GET")
        self.assertEqual(restored.operations[0].summary, "List pets")
        self.assertEqual(restored.operations[0].responses[0].status, "200")

    def test_metadata_round_trip(self):
        model = CanonicalApiModel(
            openapi_version="3.0.3",
            operations=(
                OperationFact(
                    path="/health",
                    method="GET",
                    summary=NOT_FOUND,
                    responses=(
                        ResponseFact(
                            status="200",
                            description="OK",
                        ),
                    ),
                ),
            ),
        )

        metadata = serialize_metadata(model)
        markdown = "# API\n\n" + metadata + "\n"
        restored = deserialize_metadata(markdown)

        self.assertIn("<!-- api-doc-sync-metadata:", metadata)
        self.assertTrue(metadata.endswith(" -->"))
        self.assertEqual(restored, model.normalized())

    def test_metadata_serialization_is_deterministic(self):
        model = CanonicalApiModel(
            openapi_version="3.1.0",
            operations=(
                OperationFact(
                    path="/b",
                    method="post",
                    parameters=(
                        ParameterFact(
                            name="z",
                            location="query",
                            schema={"type": "string"},
                        ),
                        ParameterFact(
                            name="a",
                            location="header",
                            schema={"type": "integer"},
                        ),
                    ),
                ),
                OperationFact(
                    path="/a",
                    method="get",
                ),
            ),
        )

        first = serialize_metadata(model)
        second = serialize_metadata(model)

        self.assertEqual(first, second)
        restored = deserialize_metadata(first)
        self.assertEqual(
            tuple(parameter.name for parameter in restored.operations[0].parameters),
            ("z", "a"),
        )

    def test_nested_collections_have_stable_order(self):
        model = CanonicalApiModel(
            schemas=(
                SchemaFact(name="Zed", schema={"type": "object"}),
                SchemaFact(name="Alpha", schema={"type": "string"}),
            ),
            paths=(
                PathFact(path="/z", summary="Z"),
                PathFact(path="/a", summary="A"),
            ),
            operations=(
                OperationFact(
                    path="/pets",
                    method="get",
                    responses=(
                        ResponseFact(status="500", description="Error"),
                        ResponseFact(status="200", description="OK"),
                    ),
                ),
            ),
        )

        normalized = model.normalized()

        self.assertEqual(
            tuple(path.path for path in normalized.paths),
            ("/z", "/a"),
        )
        self.assertEqual(
            tuple(schema.name for schema in normalized.schemas),
            ("Zed", "Alpha"),
        )
        self.assertEqual(
            tuple(response.status for response in normalized.operations[0].responses),
            ("500", "200"),
        )

    def test_declared_path_and_operation_order_is_preserved(self):
        model = CanonicalApiModel(
            paths=(
                PathFact(path="/z-last", summary="Z"),
                PathFact(path="/a-first", summary="A"),
            ),
            operations=(
                OperationFact(path="/z-last", method="POST"),
                OperationFact(path="/a-first", method="GET"),
            ),
        )

        normalized = model.normalized()

        self.assertEqual(
            tuple(path.path for path in normalized.paths),
            ("/z-last", "/a-first"),
        )
        self.assertEqual(
            tuple(operation.path for operation in normalized.operations),
            ("/z-last", "/a-first"),
        )

    def test_missing_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "metadata was not found"):
            deserialize_metadata("# API\n")

    def test_invalid_metadata_version_is_rejected(self):
        import base64
        import json

        payload = json.dumps({"model_version": 999, "paths": []}).encode("utf-8")
        encoded = base64.urlsafe_b64encode(payload).decode("ascii")

        with self.assertRaisesRegex(ValueError, "Unsupported"):
            deserialize_metadata(
                f"<!-- api-doc-sync-metadata:{encoded} -->"
            )

    def test_from_dict_preserves_missing_values(self):
        model = CanonicalApiModel.from_dict(
            {
                "openapi_version": None,
                "paths": [{"path": None, "summary": ""}],
                "operations": [{"path": None, "method": None, "summary": None}],
                "schemas": [],
            }
        )

        self.assertEqual(model.openapi_version, NOT_FOUND)
        self.assertEqual(model.paths[0].path, NOT_FOUND)
        self.assertEqual(model.operations[0].method, NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
