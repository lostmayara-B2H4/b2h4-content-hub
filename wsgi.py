"""WSGI entry point for Render.
Render auto-detecta wsgi.py e roda: gunicorn wsgi:app
"""
import os
import sys

# Adiciona scripts/ ao path (mesmo que app.py faz)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from app import app as application

if __name__ == '__main__':
    application.run()
