from flask import Flask, request, jsonify
from sc import MongoDBManager  # 确保导入的是正确的 MongoDBManager 类

app = Flask(__name__)

# 初始化 MongoDBManager
manager = MongoDBManager()
if not manager.connect():
    raise Exception("无法连接到 MongoDB 数据库")


# 根路由
@app.route('/')
def index():
    return jsonify({"message": "欢迎使用 MongoDB 管理 API", "status": "运行中"})


# 启动 API 服务
@app.route('/api/start-api', methods=['GET'])
def start_api():
    manager.start_api()  # 使用 start_api 方法启动 API 服务
    return jsonify({"message": "API服务已启动，监听端口5000"})


# 查询用户数据
@app.route('/api/query', methods=['POST'])
def query_data():
    data = request.json
    uids = data.get("uids", [])
    data_type = data.get("type", "all")

    results = {}
    for uid in uids:
        user_data = {}
        if data_type in ["user", "all"]:
            user_data["用户排名"] = manager.get_user_rank(uid)
        if data_type in ["car", "all"]:
            user_data["车辆分数"] = manager.get_car_scores(uid)
        if data_type in ["rank-list", "all"]:
            user_data["比赛记录"] = manager.get_recent_rank_list(uid)
        results[uid] = user_data

    return jsonify(results)


# 更新用户排名
@app.route('/api/update-user', methods=['POST'])
def update_user():
    data = request.json
    uid = data.get("uid")
    score = data.get("score")
    level = data.get("level")

    result = manager.update_user_rank(uid, score, level)
    return jsonify(result or {"message": "更新失败或数据未改变"})


# 更新车辆分数
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


# 更新比赛记录
@app.route('/api/update-rank-list', methods=['POST'])
def update_rank_list():
    data = request.json
    uid = data.get("uid")
    new_list = data.get("new_list")

    result = manager.update_recent_rank_list(uid, new_list)
    return jsonify(result)


# 批量更新比赛记录
@app.route('/api/batch-update-rank-list', methods=['POST'])
def batch_update_rank_list():
    data = request.json
    uids = data.get("uids", [])
    new_list = data.get("new_list")

    results = manager.batch_update_recent_rank_list(uids, new_list)
    return jsonify(results)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)


class APIService:
    pass