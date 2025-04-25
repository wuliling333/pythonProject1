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


@app.route('/query', methods=['POST'])
def query():
    try:
        data = request.get_json(force=True, silent=True) or request.form
        # 支持单个 uid 或多个 uids 查询
        uid = data.get('uid')
        uids = data.get('uids')
        query_type = data.get('type', 'all')

        results = {}

        if uids:
            # 批量查询，uids 应该是列表或逗号分隔字符串
            if isinstance(uids, str):
                uids = [int(x.strip()) for x in uids.split(',') if x.strip().isdigit()]
            elif isinstance(uids, list):
                uids = [int(x) for x in uids if isinstance(x, int) or (isinstance(x, str) and x.isdigit())]
            else:
                return jsonify({'success': False, 'error': 'uids 格式错误，应该是列表或逗号分隔字符串'})

            results = {}
            for single_uid in uids:
                user_data = {}
                if query_type in ["user", "all"]:
                    user_data["user_rank"] = manager.get_user_rank(single_uid)
                if query_type in ["car", "all"]:
                    user_data["car_scores"] = manager.get_car_scores(single_uid)
                if query_type in ["rank-list", "all"]:
                    user_data["rank_list"] = manager.get_recent_rank_list(single_uid)
                results[str(single_uid)] = user_data

        elif uid:
            uid = int(uid)
            if query_type in ["user", "all"]:
                results["user_rank"] = manager.get_user_rank(uid)
            if query_type in ["car", "all"]:
                results["car_scores"] = manager.get_car_scores(uid)
            if query_type in ["rank-list", "all"]:
                results["rank_list"] = manager.get_recent_rank_list(uid)
        else:
            return jsonify({'success': False, 'error': '未提供 uid 或 uids 参数'})

        return jsonify({'success': True, 'data': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/update-user', methods=['POST'])
def update_user():
    try:
        data = request.get_json(force=True)
        uid = data.get('uid')
        score = data.get('score')
        level = data.get('level')

        if not all([uid is not None, score is not None, level is not None]):
            return jsonify({'success': False, 'error': '参数不完整'})

        result = manager.update_user_rank(uid, score, level)
        return jsonify({'success': bool(result), 'data': result})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/car/batch-update-user-cars', methods=['POST'])
def batch_update_user_cars():
    try:
        # 统一处理不同格式的请求数据
        if request.content_type == 'application/json':
            data = request.get_json(force=True)
        else:
            data = request.form.to_dict()
            if 'updates' in data:
                try:
                    data['updates'] = json.loads(data['updates'])
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'error': 'updates参数必须是合法JSON'})

        uid = data.get('uid')
        updates = data.get('updates')

        # 参数校验
        if not uid or not updates:
            return jsonify({'success': False, 'error': '缺少uid或updates参数'})

        # 统一处理字符串/对象格式的updates
        if isinstance(updates, str):
            try:
                updates = json.loads(updates)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'updates不是有效的JSON'})

        # 调用MongoDB更新逻辑
        result = manager.batch_update_cars_for_user(int(uid), updates)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': f'服务器错误: {str(e)}'})



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

        if not isinstance(new_list, list):
            return jsonify({'success': False, 'error': 'new_list 应该是列表格式'})

        result = manager.batch_update_recent_rank_list(uids, new_list)
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
