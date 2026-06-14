"""
LoraTool - About Page
"""
from flask import Blueprint, render_template
from config import (
    SOFTWARE_VERSION, SOFTWARE_DATE,
    AUTHOR_NAME, AUTHOR_PLATFORM,
    AUTHOR_BILIBILI, SOFTWARE_DESC,
)

about_bp = Blueprint('about', __name__)


@about_bp.route('/')
def index():
    return render_template(
        'about.html',
        active_page='about',
        SOFTWARE_VERSION=SOFTWARE_VERSION,
        SOFTWARE_DATE=SOFTWARE_DATE,
        AUTHOR_NAME=AUTHOR_NAME,
        AUTHOR_PLATFORM=AUTHOR_PLATFORM,
        AUTHOR_BILIBILI=AUTHOR_BILIBILI,
        SOFTWARE_DESC=SOFTWARE_DESC,
    )
