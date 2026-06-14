"""
LoraTool - Route Registration
"""
from flask import Flask, redirect, url_for
from routes.face_split import face_split_bp
from routes.rename import rename_bp
from routes.resize import resize_bp
from routes.string_ops import string_ops_bp
from routes.label_edit import label_edit_bp
from routes.qwen_label import qwen_label_bp
from routes.qwen_vl_label import qwen_vl_label_bp
from routes.about import about_bp
from routes.tools import tools_bp


def register_routes(app: Flask):
    """Register all blueprints."""

    @app.route('/')
    def index():
        return redirect(url_for('about.index'))

    app.register_blueprint(face_split_bp, url_prefix='/face_split')
    app.register_blueprint(rename_bp, url_prefix='/rename')
    app.register_blueprint(resize_bp, url_prefix='/resize')
    app.register_blueprint(string_ops_bp, url_prefix='/string_ops')
    app.register_blueprint(label_edit_bp, url_prefix='/label_edit')
    app.register_blueprint(qwen_label_bp, url_prefix='/qwen_label')
    app.register_blueprint(qwen_vl_label_bp, url_prefix='/qwen_vl_label')
    app.register_blueprint(about_bp, url_prefix='/about')
    app.register_blueprint(tools_bp, url_prefix='/tools')
