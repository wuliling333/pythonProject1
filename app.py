import os
from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from sc import MongoDBManager
import json
from flask_cors import CORS


app = Flask(__name__)
CORS(app)  # 允许跨域请求，解决前端跨域问题

# 获取当前工作目录的绝对路径
current_directory = os.path.abspath(os.getcwd())
# 设置 Flask 模板文件夹为当前目录，方便渲染模板
app.template_folder = current_directory

# 初始化 MongoDB 管理器实例
manager = MongoDBManager()
manager.connect()  # 连接 MongoDB 数据库

@app.route('/')
def index():
    # 根路由，返回模板文件 yc.html，作为首页
    return render_template('yc.html')

# 查询用户排名和车辆分数
@app.route('/query', methods=['GET'])
def query():
    try:
        uids = request.args.get('uids')
        query_type = request.args.get('type', 'all')

        if not uids:
            return jsonify({'success': False, 'error': '缺少uids参数'})

        uids = [int(uid.strip()) for uid in uids.split(',') if uid.strip().isdigit()]

        results = {}
        for uid in uids:
            user_data = {}
            if query_type in ["user", "all"]:
                user_data["user_rank"] = manager.get_user_rank(uid)
            if query_type in ["car", "all"]:
                user_data["car_scores"] = manager.get_car_scores(uid)
            if query_type in ["rank-list", "all"]:
                user_data["rank_list"] = manager.get_recent_rank_list(uid)
            results[str(uid)] = user_data

        return jsonify({'success': True, 'data': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 更新用户排名和分数
@app.route('/update-user', methods=['POST'])
def update_user():
    try:
        # 获取请求数据
        data = request.get_json(force=True)

        # 提取参数并进行初步验证
        uid = data.get('uid')
        score = data.get('score')
        level = data.get('level')

        # 检查参数完整性
        if not all([uid is not None, score is not None, level is not None]):
            return jsonify({
                'success': False,
                'error': '参数不完整',
                'data': {
                    'uid': uid,
                    'score': score,
                    'level': level
                }
            }), 400  # 返回400状态码表示请求错误

        # 验证参数类型（确保它们是整数）
        try:
            uid = int(uid)
            score = int(score)
            level = int(level)
        except ValueError:
            return jsonify({
                'success': False,
                'error': '参数类型错误，uid、score和level必须为整数'
            }), 400

        # 执行更新操作
        result = manager.update_user_rank(uid, score, level)

        # 构造响应数据
        response = {
            'success': True,
            'data': result
        }

        return jsonify(response)

    except Exception as e:
        # 捕获所有异常并返回错误信息
        return jsonify({
            'success': False,
            'error': f'更新失败: {str(e)}'
        }), 500  # 返回500状态码表示服务器错误

# 修改车辆排位分和殿堂分
@app.route('/car/batch-update-user-cars', methods=['POST'])
def batch_update_user_cars():
    try:
        data = request.get_json(force=True)
        uid = data.get('uid')
        updates = data.get('updates')

        if not uid or not updates:
            return jsonify({'success': False, 'error': '缺少参数'})

        result = manager.batch_update_cars_for_user(uid, updates)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 修改比赛排名
@app.route('/rank-list/batch-update-list', methods=['POST'])
def batch_update_rank_list():
    try:
        data = request.get_json(force=True)
        uids = data.get('uids')
        new_list = data.get('new_list')

        if not uids or not new_list:
            return jsonify({'success': False, 'error': '参数不完整'})

        if isinstance(uids, str):
            uids = [int(x.strip()) for x in uids.split(',') if x.strip().isdigit()]
        elif isinstance(uids, list):
            uids = [int(x) for x in uids if isinstance(x, int) or (isinstance(x, str) and x.isdigit())]
        else:
            return jsonify({'success': False, 'error': 'uids 格式错误'})

        result = {}
        for uid in uids:
            res = manager.update_recent_rank_list(uid, new_list)
            result[uid] = res

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)