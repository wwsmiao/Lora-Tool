"""
LoraTool - About Page
"""
from flask import Blueprint, render_template

about_bp = Blueprint('about', __name__)


@about_bp.route('/')
def index():
    return render_template('about.html', active_page='about')
