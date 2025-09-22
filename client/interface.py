from flask import Flask, jsonify, request
from updata import send_sensor_data,send_operation_log_data

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "Flask app running on port 5006!"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5006, debug=True)


