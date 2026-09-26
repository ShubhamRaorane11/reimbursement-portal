"""
Application entry point from workspace root.
Sets working directory and delegates execution to reimbursement_portal/run.py
"""
import os
import sys

portal_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reimbursement_portal')
if portal_dir not in sys.path:
    sys.path.insert(0, portal_dir)

os.chdir(portal_dir)

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
