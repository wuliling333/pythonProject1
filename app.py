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

def validate_request(data, required_fields):
    """验证请求参数"""
    missing = [field for field in required_fields if field not in data]
    if missing:
        return False, {"status": "error", "message": f"缺少必要参数: {', '.join(missing)}", "code": 400}
    return True, None

# 根路由
@app.route('/')
def index():
    return render_template('yc.html')

# 查询用户排名和车辆分数
@app.route('/api/query', methods=['POST'])
def query_data():
    try:
        data = request.json
        uids = data.get("uids", [])
        query_type = data.get("query_type", "all")

        if not uids:
            return jsonify({"status": "error", "message": "缺少用户ID列表", "code": 400}), 400

        results = {}
        for uid in uids:
            user_data = {}
            if query_type in ["user", "all"]:
                user_rank = manager.get_user_rank(uid)
                user_data["user_rank"] = user_rank if user_rank else None
            if query_type in ["car", "all"]:
                car_scores = manager.get_car_scores(uid)
                user_data["car_scores"] = car_scores if car_scores else None
            if query_type in ["rank-list", "all"]:
                recent_rank_list = manager.get_recent_rank_list(uid)
                user_data["recent_rank_list"] = recent_rank_list if recent_rank_list else None
            results[uid] = user_data

        return jsonify(results)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "code": 500}), 500



# 更新用户排名
@app.route('/api/update-user-rank', methods=['POST'])
def update_user_rank():
    data = request.json
    valid, error = validate_request(data, ["uid", "score", "level"])
    if not valid:
        return jsonify(error), 400

    uid = data['uid']
    score = data['score']
    level = data['level']
    result = manager.update_user_rank(uid, score, level)

    if result:
        return jsonify({"status": "success", "data": result})
    else:
        return jsonify({"status": "error", "message": "更新失败或数据未改变"}), 400

# 更新车辆分数
@app.route('/api/update-car-scores', methods=['POST'])
def update_car_scores():
    data = request.json
    valid, error = validate_request(data, ["uid", "car_id", "rank_score", "season_score"])
    if not valid:
        return jsonify(error), 400

    uid = data['uid']
    car_id = data['car_id']
    rank_score = data['rank_score']
    season_score = data['season_score']
    result = manager.update_car_scores(uid, car_id, rank_score, season_score)

    if result['success']:
        return jsonify({"status": "success", "data": result['data']})
    else:
        return jsonify({"status": "error", "message": result.get("error", "更新失败")}), 400

# 批量更新车辆分数
@app.route('/api/batch-update-cars', methods=['POST'])
def batch_update_cars():
    data = request.json
    valid, error = validate_request(data, ["uid", "updates"])
    if not valid:
        return jsonify(error), 400

    uid = data['uid']
    updates = data['updates']
    result = manager.batch_update_cars_for_user(uid, updates)

    if result['success']:
        return jsonify({"status": "success", "data": result['data']})
    else:
        return jsonify({"status": "error", "message": result.get("error", "批量更新失败")}), 400

# 更新比赛记录
@app.route('/api/update-rank-list', methods=['POST'])
def update_rank_list():
    data = request.json
    valid, error = validate_request(data, ["uid", "new_list"])
    if not valid:
        return jsonify(error), 400

    uid = data['uid']
    new_list = data['new_list']
    result = manager.update_recent_rank_list(uid, new_list)

    if result['success']:
        return jsonify({"status": "success", "data": result['data']})
    else:
        return jsonify({"status": "error", "message": result.get("error", "更新失败")}), 400

# 组合更新
@app.route('/api/combo-update', methods=['POST'])
def combo_update():
    data = request.json
    valid, error = validate_request(data, ["uids", "car_id", "rank_score", "season_score", "rank_list"])
    if not valid:
        return jsonify(error), 400

    uids = data['uids']
    car_id = data['car_id']
    rank_score = data['rank_score']
    season_score = data['season_score']
    rank_list = data['rank_list']

    results = {}
    for uid in uids:
        car_result = manager.update_car_scores(uid, car_id, rank_score, season_score)
        rank_result = manager.update_recent_rank_list(uid, rank_list)
        results[uid] = {
            'car_update': car_result,
            'rank_update': rank_result
        }

    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
    app.run(debug=True)