"""
LoraTool - Other Tools Page (Friend Links)
"""
from flask import Blueprint, render_template

tools_bp = Blueprint('tools', __name__)


@tools_bp.route('/')
def index():
    return render_template('tools.html', active_page='tools')
