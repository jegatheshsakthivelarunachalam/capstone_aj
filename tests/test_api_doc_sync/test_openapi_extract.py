import unittest

from src.api_doc_sync.errors import ParseError
from src.api_doc_sync.openapi import (
    LocalRefResolver,
    extract_openapi_model,
    validate_openapi_document,
)


class OpenAPIExtractionTests(unittest.TestCase):
    def sample_spec(self):
        return {
            "openapi": "3.1.0",
            "components": {
                "schemas": {
                    "Pet": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    },
                }
            },
            "paths": {
                "/pets": {
                    "summary": "Pet operations",
                    "parameters": [
                        {
                            "name": "trace",
                            "in": "header",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ],
                    "get": {
                        "summary": "List pets",
                        "parameters": [
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "OK",
                                "headers": {
                                    "X-Rate-Limit": {
                                        "required": True,
                                        "schema": {"type": "integer"},
                                    }
                                },
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Pet"}
                                    }
                                },
                            },
                            "500": {"description": "Server error"},
                        },
                    },
                }
            },
        }

    def test_extracts_approved_fields(self):
        model = extract_openapi_model(self.sample_spec())

        self.assertEqual(model.openapi_version, "3.1.0")
        self.assertEqual(model.paths[0].path, "/pets")
        operation = model.operations[0]
        self.assertEqual(operation.method, "GET")
        self.assertEqual(operation.summary, "List pets")
        self.assertEqual(
            tuple(parameter.name for parameter in operation.parameters),
            ("trace", "limit"),
        )
        self.assertEqual(operation.responses[0].status, "200")
        self.assertEqual(operation.responses[0].headers[0].name, "X-Rate-Limit")
        self.assertEqual(
            operation.responses[0].schemas[0].schema["properties"]["name"]["type"],
            "string",
        )

    def test_rejects_unsupported_openapi_version(self):
        with self.assertRaises(ParseError):
            validate_openapi_document({"openapi": "2.0", "paths": {}})

    def test_rejects_missing_paths(self):
        with self.assertRaises(ParseError):
            validate_openapi_document({"openapi": "3.0.3"})

    def test_rejects_more_than_500_paths(self):
        spec = {"openapi": "3.0.3", "paths": {f"/p{i}": {} for i in range(501)}}
        with self.assertRaisesRegex(ParseError, "500 paths"):
            validate_openapi_document(spec)

    def test_rejects_more_than_500_schemas(self):
        spec = {
            "openapi": "3.0.3",
            "paths": {},
            "components": {
                "schemas": {f"S{i}": {"type": "string"} for i in range(501)}
            },
        }
        with self.assertRaisesRegex(ParseError, "500 schemas"):
            validate_openapi_document(spec)

    def test_missing_operation_fields_use_not_found(self):
        model = extract_openapi_model(
            {
                "openapi": "3.0.3",
                "paths": {"/empty": {"post": {}}},
            }
        )
        operation = model.operations[0]

        self.assertEqual(operation.summary, "Not Found")
        self.assertEqual(operation.request_body, None)
        self.assertEqual(operation.responses, ())

    def test_external_ref_is_not_resolved(self):
        resolver = LocalRefResolver()
        spec = {"components": {"schemas": {}}}
        resolved = resolver.resolve_schema(
            {"$ref": "https://example.com/schemas/Pet.json"},
            spec,
        )
        self.assertEqual(resolved, {"type": "Not Found"})

    def test_local_ref_resolves_to_depth(self):
        resolver = LocalRefResolver()
        spec = {
            "components": {
                "schemas": {
                    "Pet": {"type": "object", "properties": {"id": {"type": "integer"}}}
                }
            }
        }
        resolved = resolver.resolve_schema(
            {"$ref": "#/components/schemas/Pet"},
            spec,
        )
        self.assertEqual(resolved["properties"]["id"]["type"], "integer")

    def test_circular_ref_is_marked_not_found(self):
        resolver = LocalRefResolver()
        spec = {
            "components": {
                "schemas": {
                    "A": {"$ref": "#/components/schemas/B"},
                    "B": {"$ref": "#/components/schemas/A"},
                }
            }
        }
        resolved = resolver.resolve_schema(
            {"$ref": "#/components/schemas/A"},
            spec,
        )
        self.assertEqual(resolved, {"type": "Not Found"})


if __name__ == "__main__":
    unittest.main()
