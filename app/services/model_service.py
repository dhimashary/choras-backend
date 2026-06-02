import logging
import os
import uuid
import zipfile
from app.factory.geometry_converter_factory.GeometryConversionFactory import GeometryConversionFactory
import config

from flask_smorest import abort
from werkzeug.utils import secure_filename

from app.db import db
from app.models import Model, File, ModelIssue
from app.types import DetectionStage
from app.services.geometry_service import convert_repaired_obj_to_gmsh_geo, detect_geometry_issues, generate_repaired_obj_and_issue_report
from app.services.geometry_export_service import export_geometry_issues_to_json
from config import FeatureToggle, DefaultConfig
from datetime import datetime

# Create logger for this module
logger = logging.getLogger(__name__)


def create_new_model(model_data):
    new_model = Model(
        name=model_data["name"],
        projectId=model_data["projectId"],
        sourceFileId=model_data["sourceFileId"],
        outputFileId=model_data["sourceFileId"],
        imagePath=model_data["imagePath"] if "imagePath" in model_data else None,
    )
    
    

    if FeatureToggle.is_enabled("enable_geo_conversion"):
        new_model.hasGeo = True

    try:
        db.session.add(new_model)
        db.session.commit()

        # Detect geometry issues and store in ModelIssue
        directory = DefaultConfig.UPLOAD_FOLDER
        file = File.query.filter_by(id=model_data["sourceFileId"]).first()
        if file:
            file_name, file_extension = os.path.splitext(os.path.basename(file.fileName))
            obj_path = os.path.join(directory, f"{file_name}.obj")
            rhino3dm_path = os.path.join(directory, f"{file_name}.3dm")
            geo_path = os.path.join(directory, f"{file_name}.geo")
            zip_file_path = os.path.join(directory, f"{file_name}.zip")

            try:
                detected_geometry_issues = detect_geometry_issues(obj_path, rhino3dm_path)
                issue_report_path, issue_count = export_geometry_issues_to_json(detected_geometry_issues, obj_path)
                model_issue = ModelIssue(
                    modelId=new_model.id,
                    fileName=f"{file_name}_issues.json",
                    issueCount=issue_count,
                    detectionStage=DetectionStage.AfterUpload
                )
                
                db.session.add(model_issue)
                db.session.commit()
                logger.warning(f"Geometry issues detected for model {new_model.id}: {issue_count} issues found. Issue report generated at: {issue_report_path}")
                conversion_factory = GeometryConversionFactory()
                conversion_strategy = conversion_factory.create_strategy('.obj')
                
                repaired_obj_path, issue_report_path = generate_repaired_obj_and_issue_report(obj_path, rhino3dm_path, tol=1e-2, conformize_tol=None)
                logger.warning(f"Repaired OBJ file generated at: {repaired_obj_path}")
                if not conversion_strategy.generate_3dm(repaired_obj_path, rhino3dm_path):
                    logger.error("Can not generate a 3dm file")
                    return False
                logger.warning(f"Generated .geo file at: {geo_path}")
                if not convert_repaired_obj_to_gmsh_geo(repaired_obj_path, geo_path, rhino3dm_path):
                    logger.error("Can not generate a geo file")
                    return False
                
                # create a zip file from the repaired version
                with zipfile.ZipFile(zip_file_path, "w") as zipf:
                    zipf.write(rhino3dm_path, arcname=f"{file_name}.3dm") 
            except Exception as ex:
                logger.warning(f"Failed to detect geometry issues for model {new_model.id}: {ex}")

    except Exception as ex:
        db.session.rollback()
        logger.error(f"Can not create a new model: {ex}")
        abort(400, f"Can not create a new model: {ex}")

    return new_model


def get_model(model_id):
    model = Model.query.filter_by(id=model_id).first()
    if not model:
        logger.error("Model with id " + str(model_id) + "does not exists!")
        abort(404, "Model does not exist")
    return model


def update_model(model_id, model_data):
    model = Model.query.filter_by(id=model_id).first()
    if not model:
        logger.error("Model doesn't exist, cannot update!")
        abort(400, "Model doesn't exist, cannot update!")

    try:
        model.name = model_data["name"]
        model.updatedAt = datetime.now()
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        logger.error(f"Can not update! Error: {ex}")
        abort(400, message=f"Can not update! Error: {ex}")

    return model


def delete_model(model_id):
    model = Model.query.filter_by(id=model_id).first()
    if not model:
        logger.error("Model doesn't exist, cannot delete!")
        abort(404, "Model doesn't exist, cannot delete!")

    # Attempt to remove associated image asset if present
    if model.imagePath:
        image_path = model.imagePath
        # Build absolute path when a relative uploads path is stored
        if not os.path.isabs(image_path):
            image_path = os.path.join(config.basedir, image_path)
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as ex:
            # Log and continue deleting the model even if file removal fails
            logger.warning(f"Failed to remove image asset '{image_path}': {ex}")

    try:
        db.session.delete(model)
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        logger.error(f"Error deleting the model!: {ex}")
        abort(500, f"Error deleting the model!: {ex}")


def upload_image(files):
    if 'file' not in files:
        logger.error("No file provided in the request")
        abort(400, message="No file provided")
    
    upload_file = files['file']
    
    if upload_file.filename == "":
        logger.error("No file selected")
        abort(400, message="No file selected")
    
    # Check if file has allowed extension
    allowed_image_extensions = {'png', 'jpg', 'jpeg'}
    if not ('.' in upload_file.filename and 
            upload_file.filename.rsplit('.', 1)[1].lower() in allowed_image_extensions):
        logger.error(f"File type not allowed: {upload_file.filename}")
        abort(400, message="Invalid file type. Allowed types: png, jpg, jpeg")
    
    try:
        # Secure the filename and create unique name
        filename = secure_filename(upload_file.filename)
        file_ext = filename.rsplit(".", 1)[1].lower()
        unique_filename = f"{filename.rsplit('.', 1)[0]}_{uuid.uuid4().hex}.{file_ext}"
        
        # Save the file
        file_path = os.path.join(DefaultConfig.USER_MODEL_IMAGE_FOLDER_NAME, unique_filename)
        upload_file.save(file_path)
        
        # Return the relative path
        return {"imagePath": f"{DefaultConfig.USER_MODEL_IMAGE_FOLDER_NAME}/{unique_filename}"}
    
    except Exception as ex:
        logger.error(f"Error uploading image file: {ex}")
        abort(500, message=f"Error uploading image file: {ex}")
