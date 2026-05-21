from flask import jsonify, request

from .blueprint import main_bp
from ..auth_service import login_required


@main_bp.route("/receive-bam-stream-message", methods=["POST"])
@login_required
def receive_stream_message():
    try:
        data = request.get_json()
        bookings = data.get("bookings", [])
        _ = bookings
        return jsonify({"status": "success", "message": "Stream message received"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
