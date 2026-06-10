from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from app.schemas.geometry_schema import (
    GeometryGetQuerySchema,
    GeometryInspectQuerySchema,
    GeometryResultQuerySchema,
    GeometrySchema,
    GeometryStartQuerySchema,
)
from app.services import geometry_compatibility_service, geometry_service

blp = Blueprint("Geometry", __name__, description="Geometry API")


@blp.route("/geometryCheck")
class GeometryList(MethodView):
    @blp.arguments(GeometryGetQuerySchema, location="query")
    @blp.response(200, GeometrySchema)
    def get(self, query_data):
        result = geometry_service.get_geometry_by_id(query_data["geometryCheckId"])
        return result

    @blp.arguments(GeometryStartQuerySchema, location="query")
    @blp.response(201, GeometrySchema)
    def post(self, geometry_data):
        result = geometry_service.start_geometry_check_task(geometry_data["fileUploadId"])
        return result


@blp.route("/geometryCheck/result")
class Geometry(MethodView):
    @blp.arguments(GeometryResultQuerySchema, location="query")
    @blp.response(200, GeometrySchema)
    def get(self, query_data):
        result = geometry_service.get_geometry_result(query_data["taskId"])
        return result


@blp.route("/geometryCheck/inspect")
class GeometryInspect(MethodView):
    @blp.arguments(GeometryInspectQuerySchema, location="query")
    def post(self, query_data):
        """Run the inspect-only pipeline (detect → diagnostic JSON, no GEO/OBJ).

        Returns the issue report verbatim. No response schema is attached
        because the top-level keys are dynamic (one per issue kind that
        actually fired) and Marshmallow ``dump`` would strip them.
        """
        report = geometry_service.run_inspect_for_file_upload(query_data["fileUploadId"])
        return jsonify(report)


@blp.route("/geometry/compatibility")
class GeometryCompatibilityList(MethodView):
    def get(self):
        """Geometry-issue compatibility for every available simulation method.

        Each entry is the CHORAS baseline merged with that method's override
        (if any). No response schema is attached because the per-issue keys
        are dynamic (one per geometry issue kind).
        """
        return jsonify(geometry_compatibility_service.get_compatibility_for_all_methods())


@blp.route("/geometry/compatibility/baseline")
class GeometryCompatibilityBaseline(MethodView):
    def get(self):
        """The authoritative CHORAS default compatibility list (pre-merge)."""
        return jsonify(geometry_compatibility_service.get_compatibility_baseline())


@blp.route("/geometry/compatibility/<string:simulation_type>")
class GeometryCompatibilityObject(MethodView):
    def get(self, simulation_type):
        """Merged geometry-issue compatibility for a single simulation method."""
        result = geometry_compatibility_service.get_compatibility_for_method(simulation_type)
        if result is None:
            abort(404, message=f"Unknown simulation type: {simulation_type}")
        return jsonify(result)
