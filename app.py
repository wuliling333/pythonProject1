import os
from flask import Flask, request, jsonify, render_template
from sc import MongoDBManager
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 初始化 MongoDBManager
manager = MongoDBManager()
if not manager.connect():
    raise Exception("无法连接到 MongoDB 数据库")

# 获取当前目录
current_directory = os.path.abspath(os.getcwd())
# 设置模板文件夹
app.template_folder = current_directory

# 根路由
@app.route('/')
def index():
    return render_template('yc.html')

# 查询用户排名和车辆分数
@app.route('/api/query', methods=['POST'])
def query_data():
    data = request.json
    uids = data.get("uids", [])
    data_type = data.get("type", "all")

    results = {}
    for uid in uids:
        user_data = {}
        if data_type in ["user", "all"]:
            user_rank = manager.get_user_rank(uid)
            user_data["用户排名"] = user_rank if user_rank else "查询失败"
        if data_type in ["car", "all"]:
            car_scores = manager.get_car_scores(uid)
            user_data["车辆分数"] = car_scores if car_scores else "查询失败"
        if data_type in ["rank-list", "all"]:
            recent_rank_list = manager.get_recent_rank_list(uid)
            user_data["比赛记录"] = recent_rank_list if recent_rank_list else "查询失败"
        results[uid] = user_data

    return jsonify(results)

# 更新用户排名和分数
@app.route('/api/update-user', methods=['POST'])
def update_user():
    data = request.json
    uid = data.get("uid")
    score = data.get("score")
    level = data.get("level")

    result = manager.update_user_rank(uid, score, level)
    return jsonify(result or {"message": "更新失败或数据未改变"})

# 修改车辆的分数和赛季分数
@app.route('/api/update-car', methods=['POST'])
def update_car():
    data = request.json
    uid = data.get("uid")
    car_id = data.get("car_id")
    rank_score = data.get("rank_score")
    season_score = data.get("season_score")

    result = manager.update_car_scores(uid, car_id, rank_score, season_score)
    return jsonify(result)

# 批量更新用户车辆
@app.route('/api/batch-update-user-cars', methods=['POST'])
def batch_update_user_cars():
    data = request.json
    uid = data.get("uid")
    updates = data.get("updates")

    result = manager.batch_update_cars_for_user(uid, updates)
    return jsonify(result)

# 更新用户的殿堂近5场分数
@app.route('/api/update-recent-palace-scores', methods=['POST'])
def update_recent_palace_scores():
    data = request.json
    uid = data.get("uid")
    updates = data.get("updates")

    result = manager.batch_update_cars_for_user(uid, updates)
    return jsonify(result)

# 修改车辆排位分和殿堂分
@app.route('/api/update-car-rank-and-palace', methods=['POST'])
def update_car_rank_and_palace():
    data = request.json
    uid = data.get("uid")
    updates = data.get("updates")

    result = manager.batch_update_cars_for_user(uid, updates)
    return jsonify(result)

# 修改比赛排名
@app.route('/api/update-rank-list', methods=['POST'])
def update_rank_list():
    data = request.json
    uid = data.get("uid")
    new_list = data.get("new_list")

    result = manager.update_recent_rank_list(uid, new_list)
    return jsonify(result)

# 批量更新比赛排名
@app.route('/api/batch-update-rank-list', methods=['POST'])
def batch_update_rank_list():
    data = request.json
    uids = data.get("uids", [])
    new_list = data.get("new_list")

    results = manager.batch_update_recent_rank_list(uids, new_list)
    return jsonify(results)

@app.route('/run-update', methods=['GET'])
def run_update():
    test_function = request.args.get('test_function')

    if not test_function:
        return jsonify({"error": "Missing test_function parameter"}), 400

    available_functions = {
        'update_user': lambda: update_user(),
        'update_car': lambda: update_car(),
        'batch_update_user_cars': lambda: batch_update_user_cars(),
        'update_recent_palace_scores': lambda: update_recent_palace_scores(),
        'update_car_rank_and_palace': lambda: update_car_rank_and_palace(),
        'update_rank_list': lambda: update_rank_list(),
        'batch_update_rank_list': lambda: batch_update_rank_list()
    }

    if test_function not in available_functions:
        return jsonify({
            "error": "Invalid test function",
            "available_functions": list(available_functions.keys())
        }), 400

    try:
        result = available_functions[test_function]()
        return jsonify({
            "success": True,
            "function": test_function,
            "result": result.json if hasattr(result, 'json') else str(result)
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "function": test_function,
            "success": False
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)

