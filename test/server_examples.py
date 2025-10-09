import random
import os
import json
import base64
import uuid
import logging
import time
from datetime import datetime,timedelta
from functools import wraps
from db_models.base import db
from flask import send_from_directory, Flask, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity,jwt_required, JWTManager, get_jwt, verify_jwt_in_request
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from external_data_server.app_factory import create_app
from pathlib import Path

load_dotenv()

app = create_app()


app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=30)

    
    

# 这是我们的自定义装饰器
def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            # 1. 验证JWT Token是否存在且有效
            verify_jwt_in_request()
            
            # 2. 提取身份和角色信息
            user_id = get_jwt_identity()
            claims = get_jwt()
            role = claims.get("role")
            
            # 检查角色是否存在，如果需要的话
            if role is None:
                return jsonify(
                    {                    
                        "code": 400,
                        "data": {},
                        "msg": "Missing role in token"
                        }
                    )

            # 3. 将提取的信息作为关键字参数传递给原始函数
            return fn(*args, user_id=user_id, role=role, **kwargs)
        
        except Exception as e:
            # 如果 verify_jwt_in_request() 失败，它会抛出异常
            return jsonify(
                {   
                    "code": 401,
                    "data": {},
                    "msg": f"{str(e)}"
                    }
                )
            
    return wrapper

# 配置日志 (假设已有，如果没有则需要添加)
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.external_api")

# --- 路径与密钥配置 ---
# 共享数据存储路径 (原有功能)
SHARED_DATA_PATH = os.getenv("SHARED_DATA_ROOT_PATH", "shared_data")
os.makedirs(SHARED_DATA_PATH, exist_ok=True)

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 设置用于JWT签名的秘钥
# 在真实的生产环境中，请务必使用一个强大且保密的秘钥
# 从环境变量读取JWT密钥，如果未设置则使用默认值（仅用于开发环境）
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-only-change-in-production")
jwt = JWTManager(app)

# 工具配置文件路径 (新功能)
# 我们需要找到位于 cognitive_model 模块中的 tools.json 文件
# ../ 表示从 external_data_server 退到 cognitive-center，再进入 cognitive_model
TOOLS_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'cognitive_model', 'tools', 'tools.json'))

# API 安全密钥 (新功能)
TOOL_API_KEY = os.getenv("TOOL_API_SECRET_KEY")
if not TOOL_API_KEY:
    logger.warning("TOOL_API_SECRET_KEY 未在 .env 文件中配置，工具管理API将不受保护！")

# --- API 安全装饰器 ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not TOOL_API_KEY: 
            return f(*args, **kwargs)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"code": 401, "message": "未提供认证头"}), 401
        
        provided_key = auth_header.split(' ')[1]
        if provided_key != TOOL_API_KEY:
            return jsonify({"code": 403, "message": "无效的API密钥"}), 403
            
        return f(*args, **kwargs)
    return decorated_function

def read_tools_file():
    """读取并解析 tools.json 文件。"""
    try:
        with open(TOOLS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 如果文件不存在或为空/损坏，返回一个标准空结构
        return {"tools": []}

def write_tools_file(data):
    """将数据写入 tools.json 文件。"""
    with open(TOOLS_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- 新增：工具管理API端点 ---

@app.route('/api/tools', methods=['GET'])
@require_api_key
def get_tools():
    """获取所有已注册的工具列表。"""
    tools_data = read_tools_file()
    return jsonify({"code": 200, "message": "成功获取工具列表", "data": tools_data.get("tools", [])})

@app.route('/api/tools', methods=['POST'])
@require_api_key
def add_tool():
    """注册一个新工具。"""
    new_tool = request.json
    if not new_tool or "name" not in new_tool:
        return jsonify({"code": 400, "message": "请求体无效或缺少'name'字段"}), 400

    tools_data = read_tools_file()
    tools_list = tools_data.get("tools", [])

    # 检查工具名称是否已存在
    if any(t["name"] == new_tool["name"] for t in tools_list):
        return jsonify({"code": 409, "message": f"工具 '{new_tool['name']}' 已存在"}), 409

    tools_list.append(new_tool)
    tools_data["tools"] = tools_list
    write_tools_file(tools_data)
    
    logger.info(f"新工具已注册: {new_tool['name']}")
    return jsonify({"code": 201, "message": "工具已成功注册", "data": new_tool}), 201

@app.route('/api/tools/<string:tool_name>', methods=['PUT'])
@require_api_key
def update_tool(tool_name):
    """更新一个现有工具的定义。"""
    update_data = request.json
    if not update_data:
        return jsonify({"code": 400, "message": "请求体不能为空"}), 400

    tools_data = read_tools_file()
    tools_list = tools_data.get("tools", [])
    
    tool_found = False
    for i, tool in enumerate(tools_list):
        if tool["name"] == tool_name:
            tools_list[i] = update_data # 完全替换
            tool_found = True
            break
    
    if not tool_found:
        return jsonify({"code": 404, "message": f"工具 '{tool_name}' 未找到"}), 404

    tools_data["tools"] = tools_list
    write_tools_file(tools_data)
    
    logger.info(f"工具已更新: {tool_name}")
    return jsonify({"code": 200, "message": "工具已成功更新", "data": update_data})

@app.route('/api/tools/<string:tool_name>', methods=['DELETE'])
@require_api_key
def delete_tool(tool_name):
    """删除一个工具。"""
    tools_data = read_tools_file()
    tools_list = tools_data.get("tools", [])
    
    original_len = len(tools_list)
    tools_list = [tool for tool in tools_list if tool["name"] != tool_name]

    if len(tools_list) == original_len:
        return jsonify({"code": 404, "message": f"工具 '{tool_name}' 未找到"}), 404

    tools_data["tools"] = tools_list
    write_tools_file(tools_data)

    logger.info(f"工具已删除: {tool_name}")
    return jsonify({"code": 200, "message": "工具已成功删除"}), 200

def create_unique_filename(directory, extension):
    os.makedirs(directory, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    unique_id = str(uuid.uuid4().hex)[:8]
    filename = f"{timestamp}_{unique_id}.{extension}"
    return os.path.join(directory, filename)

# --- API 路由 ---
@app.route('/')
def index():
    logger.info("收到对 / 的健康检查请求")
    return "External Data Server is running!"

@app.route('/api/login', methods=['POST'])
def login():
    from db_models.base import db
    from db_models.model import User
    from external_data_server.app_factory import app_context
    
    data = request.json
    entry_user_name = data.get("username", None) 
    entry_pass_word = data.get("password", None) 
    user_detial = db.session.query(User).filter_by(user_name=entry_user_name, pass_word=entry_pass_word ).first()

    if user_detial:
        user_id = user_detial.user_id 
        user_name = user_detial.user_name
        role = user_detial.role    
        
        additional_claims = {"role": role,"user_name":user_name}
        access_token = create_access_token(identity=user_id, additional_claims=additional_claims)
        response = {
            "code": 200,
            "message": "登录成功",
            "data": {
                "user_id": user_id,
                "access_token": access_token
            },
        }
        return jsonify(response)
    else:
        response = {
            "code": 201,
            "message": "账户不存在",
            "data": {},
        }
        return jsonify(response)

@app.route('/api/get_pond_list', methods=['GET'])
@auth_required 
def get_pond_list(user_id, role):
    
    mock = [
        {
            "pond_name": "一号位",
            "pond_id": "1",
            "species_list": ["shrimp"],
        },
        {
            "pond_name": "二号位",
            "pond_id": "2",
            "species_list": ["shrimp"],
        },
        
    ]
    response = {
        "code": 200,
        "msg": "sucess",
        "data": mock
    }
    return jsonify(response)

@app.route('/api/get_pond_sensor', methods=['GET'])
@auth_required 
def get_pond_sensor(user_id, role):
    pond_id = request.args.get("pond_id")
    if not pond_id:
        return jsonify({"code": 400, "msg": "Missing pond_id", "data": []})
    
    base_time = int(time.time())  # 当前时间戳
    mock_data = []

    # 初始值
    water_temperature = round(random.uniform(31.0, 32.0), 2)
    dissolved_oxygen = round(random.uniform(5.5, 6.0), 2)
    pH = round(random.uniform(7.0, 7.5), 2)
    liquid_level = round(random.uniform(0.8, 1.0), 2)
    turbidity = round(random.uniform(3.5, 4.0), 2)
    
    circulation = round(random.uniform(20, 30), 2)
    ammonia = round(random.uniform(0.001, 0.05), 3)
    nitrite = round(random.uniform(0, 0.1), 2)
    
    for i in range(100):
        data_point = {
            "pond_id": pond_id,
            "time": base_time + i * 60,
            "water_temperature": water_temperature,
            "Dissolved_oxygen": dissolved_oxygen,
            "pH": pH,
            "liquid_level": liquid_level,
            "Turbidity": turbidity,
            "circulation": circulation,
            "ammonia": ammonia,
            "nitrite": nitrite
        }
        mock_data.append(data_point)

        # 控制每个参数的小幅变化（±0.1~0.3之间随机浮动）
        water_temperature += round(random.uniform(-0.1, 0.1), 2)
        water_temperature = round(max(30.0, min(water_temperature, 34.0)),2)

        dissolved_oxygen += round(random.uniform(-0.1, 0.1), 2)
        dissolved_oxygen = round(max(6.0, min(dissolved_oxygen, 8.0)),2)

        pH += round(random.uniform(-0.05, 0.05), 2)
        pH = round(max(6.5, min(pH, 8.5)),2)

        liquid_level += round(random.uniform(-0.02, 0.02), 2)
        liquid_level = round(max(0.4, min(liquid_level, 1.2)),2)

        turbidity += round(random.uniform(-0.1, 0.1), 2)
        turbidity = round(max(0.0, min(turbidity, 3.0)),2)
        
        ammonia += round(random.uniform(-0.005, 0.005), 3)
        ammonia = round(max(0.0, min(ammonia, 0.05)),3)
        
        circulation += round(random.uniform(-0.1, 0.1), 2)
        circulation = round(max(0.0, min(circulation, 30)),2)
        
        nitrite += round(random.uniform(-0.01, 0.01), 2)
        nitrite = round(max(0.0, min(nitrite, 0.1)),2)


    # 使用最后一个数据点作为 summary mock
    latest = mock_data[-1]
    total_mock = {
        "water_temperature": latest["water_temperature"],
        "Dissolved_oxygen": latest["Dissolved_oxygen"],
        "pH": latest["pH"],
        "liquid_level": latest["liquid_level"],
        "Turbidity": latest["Turbidity"],
        "circulation": latest["circulation"],
        "ammonia": latest["ammonia"],
        "nitrite": latest["nitrite"],
    }

    response = {
        "code": 200,
        "msg": "success",
        "data": {
            "latest": total_mock,
            "sensor": mock_data,
        }
    }
    return jsonify(response)


IMAGE_FOLDER = '/usr/henry/cognitive-center/external_data_server/mock'
    
@app.route('/api/get_pond_image', methods=['GET'])
@auth_required 
def get_pond_image(user_id, role):
    
    
    
    pond_id = request.args.get("pond_id")
    if not pond_id:
        return jsonify({"code": 400, "msg": "Missing pond_id", "data": []})
    
    try:
        all_images = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith('.jpg')]
        if not all_images:
            raise Exception("No images found")
    except Exception as e:
        return jsonify({"code": 500, "msg": f"Image load error: {str(e)}", "data": []})

    base_time = int(time.time())  
    mock_data = []

    for i in range(5):
        random_img = random.choice(all_images)
        image_url = f"http://8.216.33.92:5000/static/pond_images/{random_img}"  # 提供前端可访问的路径

        data_point = {
            "area_id": "area_id",
            "area_name": i+1,
            "time": base_time + i*60,
            "image_id": str(uuid.uuid4()),
            "image_url": image_url,    
            "alive": int(round(random.uniform(15, 25), 1)), 
            "death": int(round(random.uniform(0, 1))),      
            "length": round(random.uniform(6.5, 12.5), 1),    
            "weight": round(random.uniform(1.5, 14.5), 1),                  
            "feed": True,                    
            
        }
        mock_data.append(data_point)
    total_mock = {
        "average_alive": 3506,
        "average_death": 4,
        "count": 250,
        "average_length": 7.9,
        "average_weight": 5.5,
    }

    
    
    response = {
        "code": 200,
        "msg": "sucess",
        "data": {
            "statistics": total_mock,
            "area_list":mock_data,
            }
    }
    return jsonify(response)

@app.route('/static/pond_images/<path:filename>')
def serve_pond_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

@app.route('/api/get_pond_detail', methods=['GET'])
@auth_required 
def get_pond_detail(user_id, role):
    
    pond_id = request.args.get("pond_id")
    mock = {
        "pond_name": "一号位",
        "pond_id": "1",
        "detail": {
                "pond":
                    {
                        "area": 20.0,
                        "species": {
                            "type":"shrimp",
                            "number":3506,
                            },
                    },
                "sensor":
                    {
                        "water_temperature": 31.7,
                        "Dissolved_oxygen": 4.80043,
                        "pH": 7.4,
                        "liquid_level": 0.817,
                        "Turbidity": 2.3
                    },
                "environment":
                    {
                        "time": 1753415429,
                        "region": "つくば",
                        "weather": "sunny",
                        "temperature": 35
                    },
                "stats_image" : {
                    "length" : "http://8.216.33.92:5000/static/pond_images/length/live_shrimp_size_distribution.png",
                    "weight" : "http://8.216.33.92:5000/static/pond_images/weight/live_shrimp_weight_distribution.png"
                    
                }
                    
            },
    }
    response = {
        "code": 200,
        "msg": "sucess",
        "data": mock
    }
    return jsonify(response)

@app.route('/api/get_knowledge_base_list', methods=['GET'])
@auth_required
def get_knowledge_base_list(user_id, role):
    
    
    mock = [
        {
            "knowledge_base_name": "陆上养殖",
            "knowledge_base_id": "25241d69-33fd-465d-8fd1-18d34865248c",
            "document_list": [
        "2025_06_27.txt",
        "2025_07_08.txt",
        "2025_07_14.txt",
        "2025_06_16.txt",
        "2025_06_24.txt",
        "2025_07_21.txt",
        "2025_07_07.txt",
        "2025_06_12.txt",
        "\u5faa\u73af\u6c34\u5357\u7f8e\u767d\u5bf9\u867e\u517b\u6b96\u7cfb\u7edf\u8bbe\u8ba1\u53ca\u64cd\u4f5c\u624b\u518c\u5f20\u9a70v3.0.pdf",
        "2025_07_25.txt",
        "2025_07_17.txt",
        "2025_07_15.txt",
        "2025_07_03.txt",
        "2025_07_24.txt",
        "2025_06_17.txt",
        "2025_07_16.txt",
        "2025_07_23.txt",
        "2025_06_23.txt",
        "2025_06_20.txt",
        "2025_07_09.txt",
        "2025_06_25.txt",
        "2025_07_11.txt",
        "2025_06_30.txt",
        "2025_07_10.txt",
        "2025_07_18.txt",
        "2025_07_01.txt",
        "2025_07_04.txt",
        "2025_07_02.txt",
        "2025_07_22.txt"
      ],
        },
    #     {
    #         "knowledge_base_name": "银行合规",
    #         "knowledge_base_id": "cede3e0b-6447-4418-9c80-97129710beb5",
    #         "document_list": [
    #     "POJK 13 - 2015.pdf",
    #     "SEOJK 6 - 2016.pdf",
    #     "SEOJK 30 - 2017.pdf",
    #     "pojk 13-2019.pdf",
    #     "pojk 62-2020.pdf",
    #     "SEOJK 23 - 2023.pdf",
    #     "POJK 23 - 2019.pdf",
    #     "SEOJK 50-2017.pdf",
    #     "POJK 4 - 2015.pdf",
    #     "POJK 12-2018.pdf",
    #     "POJK 38 - 2016.pdf",
    #     "Peraturan Direktur Jenderal Pajak No. PER16-PJ-2016.pdf",
    #     "POJK 37 - 2016.pdf",
    #     "SEOJK 31 - 2017.pdf",
    #     "POJK 13 - 2021.pdf",
    #     "POJK 03 - 2023.pdf",
    #     "PBPJS-5-2018.pdf",
    #     "UU Nomor 1 Tahun 2016.pdf",
    #     "PBPJS-5-2019.pdf",
    #     "POJK 3 - 2014.pdf",
    #     "POJK 48 - 2017.pdf",
    #     "POJK 12-2016.pdf",
    #     "Peraturan Direktur Jenderal Pajak No. PER04-PJ-2018.pdf",
    #     "POJK 76 - 2016.pdf",
    #     "POJK 12 - 2024.pdf",
    #     "POJK 18 - 2017.pdf",
    #     "SEOJK 1 - 2019.pdf",
    #     "POJK 23 - 2024.pdf",
    #     "SEOJK  7 - 2016.pdf",
    #     "POJK 7 Tahun 2024 Bank Perekonomian Rakyat dan Bank Perekonomian Rakyat Syariah (1).pdf",
    #     "UU Nomor 36 Tahun 2008.pdf",
    #     "POJK 03-2022.pdf",
    #     "SEOJK 12  - 2022.pdf",
    #     "SEOJK 16 - 2019.pdf",
    #     "POJK 23 - 2022.pdf",
    #     "pojk 13-2018.pdf",
    #     "POJK 9 -2024.pdf",
    #     "POJK 26 - 2024.pdf",
    #     "POJK  3 - 2023.pdf",
    #     "SEOJK 4 - 2014.pdf",
    #     "pojk 75-2016.pdf",
    #     "POJK 7 Tahun 2024 Bank Perekonomian Rakyat dan Bank Perekonomian Rakyat Syariah (1)(1).pdf",
    #     "POJK 22 - 2023.pdf",
    #     "POJK 28 -2023.pdf",
    #     "pojk 33-2018.pdf",
    #     "SEOJK 39 - 2017.pdf",
    #     "Peraturan Direktur Jenderal Pajak No. PER16-PJ-2017.pdf"
    #   ],
    #     },
    ]
    response = {
        "code": 200,
        "msg": "sucess",
        "data": mock
    }
    return jsonify(response)

@app.route('/api/get_tool_list', methods=['GET'])
@auth_required
def get_tool_list(user_id, role):
    
    
    tool_mock = [
        {"tool_id": "60dc063e-b2ee-4ec2-b5ff-8bb9e0331d61", "tool_name": "文件分析", "description": "用于分析指定路径中的文件内容", "status": "activate", "perm": "public"},
        {"tool_id": "fa5d4e87-8f47-44a4-b525-986726004e47", "tool_name": "科学计算器", "description": "用于分析并计算复杂的科学工具", "status": "activate", "perm": "private"},
    ]
    model_mock = [
        {"model_id": "2bf21219-0a53-485b-835e-b5e71b9e4185", "model_name": "gpt-4o", "description": "标准模型", "status": "activate", "perm": "public"},
        {"model_id": "81a0678e-9de3-45ca-99b7-60b19cf975f6", "model_name": "gpt-4o-mini", "description": "轻量模型", "status": "activate", "perm": "private"},
        {"model_id": "81a0678e-9de3-45ca-99b7-60b19cf975f6", "model_name": "gpt-5", "description": "先进模型", "status": "activate", "perm": "private"},
    ]
    data = {
        "model_list": model_mock,
        "tool_list": tool_mock
    }
    response = {
        "code": 200,
        "msg": "sucess",
        "data": data
    }
    return jsonify(response)

@app.route('/api/delete_session', methods=['POST'])
@auth_required
def delete_session(user_id, role):
    from db_models.base import db
    from db_models.model import Session
    
    data = request.get_json()
    session_id = data.get("session_id") 
    
    print(session_id,user_id)
    response = {
        "code": 200,
        "msg": "",
        "data": ""
    }
    if not session_id:
        response["code"] = 400
        response["msg"] = "Missing session_id"
        return jsonify(response)
    try:
        session = db.session.query(Session).filter_by(session_id=session_id, user_id=user_id).first()
        if not session:
            response["code"] = 404
            response["msg"] = f"Session {session_id} not found"
            return jsonify(response)

        db.session.delete(session)
        db.session.commit()

        response["msg"] = f"Successfully deleted session {session_id}"
        return jsonify(response)

    except Exception as e:
        db.session.rollback()
        response["code"] = 500
        response["msg"] = f"Error deleting session: {str(e)}"
        return jsonify(response)

@app.route('/api/get_session_list', methods=['GET'])
@auth_required
def get_session_list(user_id, role):
    from db_models.base import db
    from db_models.model import Session
    
    session_list = db.session.query(Session).filter_by(user_id=user_id).order_by(Session.create_at.desc()).all()
    data = [
        {
            "session_name": session.session_name,
            "session_id": session.session_id,
            "timestamp": int(session.create_at.timestamp()) if session.create_at else 0
        }
        for session in session_list
    ]

    response = {
        "code": 200,
        "msg": "success",
        "data": data
    }
    return jsonify(response)

@app.route('/api/get_device_list', methods=['GET'])
@auth_required
def get_device_list(user_id, role):
    """
    获取指定pond_id的设备列表
    """
    from db_models.base import db
    from db_models.device import Device
    from db_models.pond import Pond
    
    pond_id = request.args.get("pond_id", type=int, default=1)
    if not pond_id:
        return jsonify({"code": 400, "msg": "Missing pond_id", "data": []})
    
    try:
        # 使用联表查询获取设备信息和对应的pond名称
        data_list = db.session.query(Device, Pond.name.label('pond_name')).join(
            Pond, Device.pond_id == Pond.id
        ).filter(Device.pond_id == pond_id).order_by(Device.created_at.desc()).all()
        
        device_list = [
            {
                "device_id": device.device_id,
                "name": device.name,
                "description": device.description,
                "model": device.model,
                "manufacturer": device.manufacturer,
                "serial_number": device.serial_number,
                "location": device.location,
                "pond_name": pond_name,  # 返回pond的名称而不是pond_id
                "status": device.status,
                "switch_status": device.switch_status,
                "priority": device.priority,
                "ip_address": device.ip_address,
                "mac_address": device.mac_address,
                "firmware_version": device.firmware_version,
                "hardware_version": device.hardware_version,
                "tags": device.tags,
                "installed_at": int(device.installed_at.timestamp()) if device.installed_at else None,
                "last_maintenance_at": int(device.last_maintenance_at.timestamp()) if device.last_maintenance_at else None,
                "next_maintenance_at": int(device.next_maintenance_at.timestamp()) if device.next_maintenance_at else None,
                "warranty_expires_at": int(device.warranty_expires_at.timestamp()) if device.warranty_expires_at else None,
                "created_at": int(device.created_at.timestamp()) if device.created_at else 0,
                "updated_at": int(device.updated_at.timestamp()) if device.updated_at else 0
            }
            for device, pond_name in data_list
        ]

        data = {
            "total": len(device_list),
            "page_size": 10,
            "page": 1,
            "data": device_list
        }

        response = {
            "code": 200,
            "msg": "success",
            "data": data
        }
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"获取设备列表失败: {str(e)}")
        response = {
            "code": 500,
            "msg": f"获取设备列表失败: {str(e)}",
            "data": []
        }
        return jsonify(response)
    
@app.route('/api/update_device_switch_status', methods=['POST'])
@auth_required
def update_device_switch_status(user_id, role):
    """
    更新设备的开关状态
    """
    from db_models.base import db
    from db_models.device import Device
    
    # 获取请求参数
    device_id = request.args.get("device_id")
    switch_status = request.args.get("switch_status")
    
    # 参数验证
    if not device_id:
        return jsonify({"code": 400, "msg": "缺少设备ID参数", "data": {}})
    
    if switch_status is None:
        return jsonify({"code": 400, "msg": "缺少开关状态参数", "data": {}})

    # 验证switch_status的值（假设只允许0和1，0表示关闭，1表示开启）
    if switch_status not in ["on", "off"]:
        return jsonify({"code": 400, "msg": "开关状态参数无效，只允许on（开启）或off（关闭）", "data": {}})
    
    try:
        # 查找设备
        device = db.session.query(Device).filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"code": 404, "msg": "设备不存在", "data": {}})
        
        # 更新设备开关状态
        old_switch_status = device.switch_status
        device.switch_status = switch_status
        device.updated_at = datetime.now()
        
        # 提交数据库更改
        db.session.commit()
        
        logger.info(f"设备 {device_id} 开关状态已从 {old_switch_status} 更新为 {switch_status}")
        
        response = {
            "code": 200,
            "msg": "设备开关状态更新成功",
            "data": {
                "device_id": device.device_id,
                "name": device.name,
                "old_switch_status": old_switch_status,
                "new_switch_status": device.switch_status,
                "updated_at": int(device.updated_at.timestamp())
            }
        }
        return jsonify(response)
        
    except Exception as e:
        # 回滚数据库事务
        db.session.rollback()
        logger.error(f"更新设备开关状态失败: {str(e)}")
        response = {
            "code": 500,
            "msg": f"更新设备开关状态失败: {str(e)}",
            "data": {}
        }
        return jsonify(response)
  
    
@app.route('/api/get_session_config', methods=['POST'])
@auth_required
def session_config(user_id, role):
    session_config_detail = {
        "model_config": {
            "model_name": "gpt-4o-mini",
            "temperature": 0.7
        },
        "tool_list": [
            {
                "id": "1",
                "name": "文件分析",
                "desc": "用于分析指定路径中的文件内容",
                "status": True,
                "perm": "public"
                },
            {
                
                "id": "2",
                "name": "科学计算器",
                "desc": "用于分析并计算复杂的科学工具",
                "status": True,
                "perm": "private"
                },
            ],
        "token_count": {
            "model_name": "gpt-4o-mini",
            "temperature": 0.7
        },
        "thinking_mode": {
            "model_name": "gpt-4o-mini",
            "temperature": 0.7
        },
        "Summary_amount": {
            "model_name": "gpt-4o-mini",
            "temperature": 0.7
        },
        
        
    }  
    response = {
        "code": 200,
        "msg": "sucess",
        "data": session_config_detail
    }
    return jsonify(response)

@app.route('/api/get_task_list', methods=['GET'])
@auth_required
def get_task_list(user_id, role):
    """
    获取用户的任务列表
    通过user_id获取对应的session_id，再查询agent_task表中匹配的任务记录
    
    Args:
        user_id: 用户ID
        role: 用户角色
    
    Returns:
        JSON响应包含任务列表数据
    """
    from db_models.session import Session
    from db_models.agent_task import AgentTask
    
    try:
        # 获取用户的所有session_id
        session_list = db.session.query(Session).filter_by(user_id=user_id).order_by(Session.create_at.desc()).all()
        session_ids = [session.session_id for session in session_list]
        
        if not session_ids:
            # 如果用户没有session，返回空列表
            data = {
                "total": 0,
                "page_size": 10,
                "page": 1,
                "data": []
            }
            response = {
                "code": 200,
                "msg": "success",
                "data": data
            }
            return jsonify(response)
        
        # 根据session_ids查询对应的任务记录
        tasks = db.session.query(AgentTask).filter(
            AgentTask.session_id.in_(session_ids)
        ).order_by(AgentTask.created_at.desc()).all()
        
        # 构建返回的任务列表
        task_list = []
        for task in tasks:
            task_data = {
                "task_id": task.task_id,
                "session_id": task.session_id,
                "parent_task_id": task.parent_task_id,
                "goal": task.goal,
                "status": task.status,
                "priority": task.priority,
                "input_params": task.input_params,
                "result": task.result,
                "error_message": task.error_message,
                "logs": task.logs,
                "tool_calls": task.tool_calls,
                "token_usage": task.token_usage,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            }
            task_list.append(task_data)
        
        data = {
            "total": len(task_list),
            "page_size": 10,
            "page": 1,
            "data": task_list
        }
        
        response = {
            "code": 200,
            "msg": "success",
            "data": data
        }
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        response = {
            "code": 500,
            "msg": f"获取任务列表失败: {str(e)}",
            "data": None
        }
        return jsonify(response)
       
    
    
    
    
    
@app.route('/api/transfer_data', methods=['POST'])
def transfer_data():
    """
    接收并根据类型分类存储数据。
    """
    try:
        data = request.json
        if not data or 'type' not in data or 'content' not in data:
            return jsonify({"code": 400, "message": "请求体必须是包含 'type' 和 'content' 字段的 JSON"}), 400

        data_type = data['type']
        content = data['content']
        logger.info(f"收到保存请求，类型: '{data_type}'")
        
        filepath = "" 
        message = ""

        if data_type == "操作日志":
            log_dir = os.path.join(SHARED_DATA_PATH, "operation_logs")
            filepath = create_unique_filename(log_dir, "log")
            if isinstance(content, (dict, list)):
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(content, f, ensure_ascii=False, indent=4)
            else:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(str(content))
            message = f"操作日志已保存至 {os.path.basename(filepath)}"

        elif data_type == "传感器数据":
            sensor_dir = os.path.join(SHARED_DATA_PATH, "sensor_data")
            filepath = create_unique_filename(sensor_dir, "json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=4)
            message = f"传感器数据已保存至 {os.path.basename(filepath)}"
            
        elif data_type == "采集图像":
            image_dir = os.path.join(SHARED_DATA_PATH, "collected_images")
            try:
                header, encoded_data = content.split(',', 1)
                file_ext = header.split(';')[0].split('/')[1]
                image_data = base64.b64decode(encoded_data)
                filepath = create_unique_filename(image_dir, file_ext)
                with open(filepath, 'wb') as f:
                    f.write(image_data)
                message = f"图像已保存至 {os.path.basename(filepath)}"
            except Exception as e:
                logger.error(f"解析 Base64 图像数据失败: {e}")
                return jsonify({"code": 400, "message": "无效的 Base64 图像数据格式"}), 400
        
        else:
            logger.warning(f"收到未知的类型: '{data_type}'")
            return jsonify({"code": 400, "message": f"不支持的数据类型: '{data_type}'"}), 400

        logger.info(message)
        return jsonify({"code": 200, "message": message, "data": {"filepath": filepath}})

    except Exception as e:
        logger.exception("处理 /api/save_data 时发生错误")
        return jsonify({"code": 500, "message": "内部服务器错误"}), 500

@app.route('/api/get_files', methods=['POST'])
def get_files():
    """
    根据请求类型和文件名返回文件内容。
    """
    try:
        data = request.json
        if not data or 'type' not in data or 'filenames' not in data:
            return jsonify({"code": 400, "message": "请求体必须包含 'type' 和 'filenames' 字段"}), 400

        data_type = data['type']
        filenames = data['filenames']

        if not isinstance(filenames, list):
            return jsonify({"code": 400, "message": "'filenames' 字段必须是列表"}), 400


        # 根据类型设置对应路径
        if data_type == "操作日志":
            target_dir = os.path.join(SHARED_DATA_PATH, "operation_logs")
        elif data_type == "传感器数据":
            target_dir = os.path.join(SHARED_DATA_PATH, "sensor_data")
        elif data_type == "采集图像":
            target_dir = os.path.join(SHARED_DATA_PATH, "collected_images")
        else:
            return jsonify({"code": 400, "message": f"不支持的类型: '{data_type}'"}), 400

        # 返回文件内容
        files_data = {}
        for filename in filenames:
            file_path = os.path.join(target_dir, filename)
            print(f"data_type:{data_type} file_path:{file_path}")
            if not os.path.exists(file_path):
                files_data[filename] = {"error": "文件不存在"}
                continue

            try:
                if data_type == "采集图像":
                    # 图像以 base64 返回
                    with open(file_path, 'rb') as f:
                        encoded = base64.b64encode(f.read()).decode('utf-8')
                        mime_type = f"image/{Path(filename).suffix.lstrip('.')}"
                        files_data[filename] = f"data:{mime_type};base64,{encoded}"
                else:
                    # 其他文件以文本/JSON 形式返回
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        try:
                            # 尝试解析 JSON 格式
                            files_data[filename] = json.loads(content)
                        except json.JSONDecodeError:
                            files_data[filename] = content
            except Exception as e:
                logger.error(f"读取文件失败: {filename}, 错误: {e}")
                files_data[filename] = {"error": "读取失败"}

        return jsonify({"code": 200, "message": "文件获取成功", "data": files_data})

    except Exception as e:
        logger.exception("处理 /api/get_files 时发生错误")
        return jsonify({"code": 500, "message": "内部服务器错误"}), 500

@app.route('/api/updata_file', methods=['POST'])
def updata_file():
    """
    接收文件和类型字段，根据类型保存到对应目录
    """
    try:
        # 读取字段
        data_type = request.form.get("type")  
        file = request.files.get("file")

        if not file or not data_type:
            return jsonify({"code": 400, "message": "缺少文件或类型字段"}), 400

        # 决定保存目录
        if data_type == "操作日志":
            target_dir = os.path.join(SHARED_DATA_PATH, "operation_logs")
        elif data_type == "传感器数据":
            target_dir = os.path.join(SHARED_DATA_PATH, "sensor_data")
        elif data_type == "采集图像":
            target_dir = os.path.join(SHARED_DATA_PATH, "collected_images")
        else:
            return jsonify({"code": 400, "message": f"不支持的类型: '{data_type}'"}), 400

        # 确保目录存在
        os.makedirs(target_dir, exist_ok=True)

        # 安全保存文件
        filename = secure_filename(file.filename)
        save_path = os.path.join(target_dir, filename)
        file.save(save_path)

        logger.info(f"文件已保存: {save_path}")
        return jsonify({
            "code": 200,
            "message": "文件上传成功",
            "file_path": save_path
        }), 200

    except Exception as e:
        logger.exception("上传文件异常:")
        return jsonify({"code": 500, "message": "服务器内部错误"}), 500



# --- 启动服务器 ---
if __name__ == '__main__':
    host = os.getenv("HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("HTTP_PORT", 5000))
    logger.info(f"🚀 Flask 服务器启动，正在监听 http://{host}:{port}")
    app.run(host=host, port=port)