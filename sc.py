from pymongo import MongoClient
import argparse
import pprint
import json
from typing import Optional, Dict, Any, List, Union, Tuple


class MongoDBManager:
    """MongoDB 数据管理工具类，封装了用户排名、车辆数据和比赛记录的操作"""

    def __init__(self):
        """初始化 MongoDB 连接和打印工具"""
        self.client = None
        self.db = None
        self.pp = pprint.PrettyPrinter(indent=2)
        self.uri = (
            "mongodb://wp_dev_vnm:SrJ5gZwoLVl2@"
            "weplay-vnm.db.wepieoa.com:32201/"
            "desertsafari_api_v3?"
            "authSource=admin&"
            "directConnection=true"
        )

    def connect(self) -> bool:
        """连接 MongoDB 数据库"""
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self.db = self.client["desertsafari_api_v3"]
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if self.client:
            self.client.close()

    # ==================== 通用工具方法 ====================
    def _get_user_filter(self, uid: int) -> Dict:
        """获取用户查询条件，支持字符串和整数类型的UID"""
        return {"$or": [{"uid": uid}, {"uid": str(uid)}]}

    def _handle_db_error(self, operation: str, uid: int, e: Exception) -> None:
        """统一处理数据库错误"""
        print(f"{operation}失败(UID:{uid}): {e}")

    # ==================== UserInfo 集合操作 ====================
    def get_user_rank(self, uid: int) -> Optional[Dict[str, Any]]:
        """查询用户排名数据（修改版：使用racetrack_rank_data.rank_level）"""
        try:
            data = self.db["UserInfo"].find_one(
                {"uid": uid},
                {"_id": 0, "racetrack_rank_data.rank_score": 1, "racetrack_rank_data.rank_level": 1}
            )
            return {
                "rank_score": data["racetrack_rank_data"]["rank_score"],
                "rank_level": data["racetrack_rank_data"]["rank_level"]  # 修改这里
            } if data else None
        except Exception as e:
            self._handle_db_error("查询UserInfo", uid, e)
            return None

    def update_user_rank(self, uid: int, score: int, level: int) -> Optional[Dict[str, Any]]:
        """更新用户排名数据（修改版：使用racetrack_rank_data.rank_level）"""
        try:
            result = self.db["UserInfo"].update_one(
                {"uid": uid},
                {"$set": {
                    "racetrack_rank_data.rank_score": score,
                    "racetrack_rank_data.rank_level": level  # 修改这里
                }}
            )
            return self.get_user_rank(uid) if result.modified_count > 0 else None
        except Exception as e:
            self._handle_db_error("更新UserInfo", uid, e)
            return None

    # ==================== UserExtraInfo 集合操作 ====================
    def get_car_list(self, uid: int) -> Dict[str, Any]:
        """获取用户的car_list数据"""
        try:
            data = self.db["UserExtraInfo"].find_one(
                self._get_user_filter(uid),
                {"_id": 0, "car_garage.car_list": 1}
            )
            return data.get("car_garage", {}).get("car_list", {}) if data else {}
        except Exception as e:
            self._handle_db_error("获取车辆列表", uid, e)
            return {}

    def get_car_scores(self, uid: int) -> Dict[str, Dict[str, Any]]:
        """获取所有车辆的分数信息，并从palace_score_list提取指定索引的score到recent_palace_score"""
        car_list = self.get_car_list(uid)
        return {
            car_id: {
                'rank_score': car_data.get('rank_score', 'N/A'),
                'season_best_rank_score': car_data.get('season_best_rank_score', 'N/A'),
                # 从palace_score_list提取索引0,1,3,4的score到recent_palace_score
                'recent_palace_score': [
                    car_data.get('palace_score_list', [{}] * 5)[0].get('score', -1),
                    car_data.get('palace_score_list', [{}] * 5)[1].get('score', -1),
                    car_data.get('palace_score_list', [{}] * 5)[2].get('score', -1),
                    car_data.get('palace_score_list', [{}] * 5)[3].get('score', -1),
                    car_data.get('palace_score_list', [{}] * 5)[4].get('score', -1)
                ]
            }
            for car_id, car_data in car_list.items()
        }

    def batch_update_cars_for_user(
            self,
            uid: int,
            car_updates: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量更新车辆分数（增强版）
        参数说明：
            car_updates: {
                "car_id": {
                    "rank_score": int,
                    "season_best_rank_score": int,
                    "recent_palace_score": List[int],  # 新增支持
                    "palace_score_indices": List[int]  # 新增: 指定要提取的palace_score_list索引
                }
            }
        """
        try:
            # 获取并验证车辆列表
            current_cars = self.get_car_list(uid)
            if not current_cars:
                return {'success': False, 'error': '用户无车辆数据'}

            invalid_cars = [cid for cid in car_updates if cid not in current_cars]
            if invalid_cars:
                return {'success': False, 'error': f'以下车辆不存在: {", ".join(invalid_cars)}'}

            # 构建更新操作（新增palace_score处理）
            update_fields = {}
            for car_id, updates in car_updates.items():
                # 原有字段处理
                if 'rank_score' in updates:
                    update_fields[f"car_garage.car_list.{car_id}.rank_score"] = updates['rank_score']
                if 'season_best_rank_score' in updates:
                    update_fields[f"car_garage.car_list.{car_id}.season_best_rank_score"] = updates[
                        'season_best_rank_score']

                # 新增: 提取 palace_score_list 中指定索引的 score 值
                if 'palace_score_indices' in updates:
                    # 获取当前车辆的 palace_score_list
                    current_car = current_cars.get(car_id)
                    if not current_car or 'palace_score_list' not in current_car:
                        return {'success': False, 'error': f'车辆 {car_id} 无 palace_score_list 数据'}

                    palace_score_list = current_car['palace_score_list']
                    # 提取指定索引的 score 值
                    score = []
                    for idx in updates['palace_score_indices']:
                        if 0 <= idx < len(palace_score_list):
                            score.append(palace_score_list[idx].get('score', -1))
                        else:
                            return {'success': False, 'error': f'车辆 {car_id} 的 palace_score_list 索引 {idx} 无效'}

                    # 更新 recent_palace_score
                    update_fields[f"car_garage.car_list.{car_id}.recent_palace_score"] = score

            if not update_fields:
                return {'success': False, 'error': '无有效更新字段'}

            # 执行更新
            result = self.db["UserExtraInfo"].update_one(
                self._get_user_filter(uid),
                {"$set": update_fields}
            )

            # 返回结果增强
            if result.modified_count == 1:
                updated_data = self.get_car_scores(uid)  # 使用修改后的get_car_scores
                return_data = {}
                for car_id, updates in car_updates.items():
                    car_info = updated_data.get(car_id, {})
                    car_return_data = {}
                    if 'rank_score' in updates:
                        car_return_data['rank_score'] = car_info.get('rank_score')
                    if 'season_best_rank_score' in updates:
                        car_return_data['season_best_rank_score'] = car_info.get('season_best_rank_score')
                    if 'palace_score_indices' in updates:
                        car_return_data['score'] = car_info.get('score')
                    return_data[car_id] = car_return_data
                return {
                    'success': True,
                    'data': return_data
                }
            return {'success': False, 'error': '数据未改变'}
        except Exception as e:
            self._handle_db_error("批量更新用户车辆", uid, e)
            return {'success': False, 'error': str(e)}

    def update_car_scores(
            self,
            uid: int,
            car_id: str,
            rank_score: int,
            season_best_rank_score: int
    ) -> Dict[str, Any]:
        """更新指定车辆的分数"""
        try:
            car_list = self.get_car_list(uid)
            if not car_list or car_id not in car_list:
                return {'success': False, 'error': f'车辆 {car_id} 不存在'}

            result = self.db["UserExtraInfo"].update_one(
                self._get_user_filter(uid),
                {"$set": {
                    f"car_garage.car_list.{car_id}.rank_score": rank_score,
                    f"car_garage.car_list.{car_id}.season_best_rank_score": season_best_rank_score
                }}
            )

            if result.modified_count == 1:
                updated_data = self.get_car_list(uid)
                return {
                    'success': True,
                    'data': {
                        car_id: {
                            'rank_score': updated_data[car_id].get('rank_score'),
                            'season_best_rank_score': updated_data[car_id].get('season_best_rank_score')
                        }
                    }
                }
            return {'success': False, 'error': '数据未改变'}
        except Exception as e:
            self._handle_db_error("更新车辆分数", uid, e)
            return {'success': False, 'error': str(e)}

    def update_palace_scores(
            self,
            uid: int,
            car_updates: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量更新车辆宫殿分数
        参数说明：
            car_updates: {
                "car_id": {
                    "palace_scores": [s1, s2, s3, s4, s5]  # 要更新的5个分数
                }
            }
        """
        try:
            # 获取当前车辆列表
            current_cars = self.get_car_list(uid)
            if not current_cars:
                return {'success': False, 'error': '用户无车辆数据'}

            # 验证车辆ID
            invalid_cars = [cid for cid in car_updates if cid not in current_cars]
            if invalid_cars:
                return {'success': False, 'error': f'无效车辆ID: {", ".join(invalid_cars)}'}

            update_fields = {}
            for car_id, updates in car_updates.items():
                if 'palace_scores' in updates:
                    new_scores = updates['palace_scores']

                    # 验证输入
                    if not isinstance(new_scores, list) or len(new_scores) != 5:
                        return {'success': False, 'error': 'palace_scores必须是包含5个分数的列表'}

                    # 构建完整的更新数组
                    current_list = current_cars[car_id].get('palace_score_list', [{}] * 5)
                    if len(current_list) < 5:
                        current_list.extend([{}] * (5 - len(current_list)))

                    updated_list = []
                    for i in range(5):
                        # 保留原有protect_state和invalid字段，只更新score
                        updated_item = {
                            "score": new_scores[i],
                            "protect_state": current_list[i].get("protect_state", 0),
                            "invalid": current_list[i].get("invalid", False)
                        }
                        updated_list.append(updated_item)

                    update_fields[f"car_garage.car_list.{car_id}.palace_score_list"] = updated_list

            if not update_fields:
                return {'success': False, 'error': '无有效更新字段'}

            # 执行更新
            result = self.db["UserExtraInfo"].update_one(
                self._get_user_filter(uid),
                {"$set": update_fields}
            )

            if result.modified_count > 0:
                return {
                    'success': True,
                    'data': {
                        car_id: {
                            'palace_score_list': updates.get('palace_scores')
                        }
                        for car_id, updates in car_updates.items()
                    }
                }
            return {'success': False, 'error': '数据未改变'}

        except Exception as e:
            self._handle_db_error("批量更新殿堂分数", uid, e)
            return {'success': False, 'error': f'系统错误: {str(e)}'}

    # ==================== recent_rank_list 操作 ====================
    def get_recent_rank_list(self, uid: int) -> Optional[List[Union[Dict[str, Any], int]]]:
        """获取用户的最近比赛排名列表"""
        try:
            data = self.db["UserExtraInfo"].find_one(
                self._get_user_filter(uid),
                {"_id": 0, "racetrack_match_data.recent_rank_list": 1}
            )
            return data.get("racetrack_match_data", {}).get("recent_rank_list", []) if data else []
        except Exception as e:
            self._handle_db_error("获取比赛记录", uid, e)
            return None

    def update_recent_rank_list(
            self,
            uid: int,
            new_list: List[Union[Dict[str, Any], int]]
    ) -> Dict[str, Any]:
        """更新整个比赛排名列表"""
        try:
            result = self.db["UserExtraInfo"].update_one(
                self._get_user_filter(uid),
                {"$set": {"racetrack_match_data.recent_rank_list": new_list}}
            )
            return {
                'success': result.modified_count == 1,
                'data': new_list,
                'error': None if result.modified_count == 1 else '数据未改变'
            }
        except Exception as e:
            self._handle_db_error("更新比赛记录", uid, e)
            return {'success': False, 'error': str(e)}

    def batch_update_recent_rank_list(
            self,
            uids: List[int],
            new_list: List[Union[Dict[str, Any], int]]
    ) -> Dict[int, Dict[str, Any]]:
        """批量更新多个用户的比赛排名列表"""
        return {uid: self.update_recent_rank_list(uid, new_list) for uid in uids}

    def update_single_record(
            self,
            uid: int,
            index: int,
            new_value: Union[Dict[str, Any], int]
    ) -> Dict[str, Any]:
        """更新单个比赛记录"""
        try:
            current_list = self.get_recent_rank_list(uid) or []
            if not 0 <= index < len(current_list):
                return {
                    'success': False,
                    'error': f'索引 {index} 超出范围（0-{len(current_list) - 1}）'
                }

            current_list[index] = new_value
            result = self.db["UserExtraInfo"].update_one(
                self._get_user_filter(uid),
                {"$set": {"racetrack_match_data.recent_rank_list": current_list}}
            )

            return {
                'success': result.modified_count == 1,
                'data': current_list,
                'error': None if result.modified_count == 1 else '数据未改变'
            }
        except Exception as e:
            self._handle_db_error("更新比赛记录项", uid, e)
            return {'success': False, 'error': str(e)}

    def batch_update_single_record(
            self,
            uids: List[int],
            index: int,
            new_value: Union[Dict[str, Any], int]
    ) -> Dict[int, Dict[str, Any]]:
        """批量更新多个用户的单个比赛记录"""
        return {uid: self.update_single_record(uid, index, new_value) for uid in uids}
    def get_palace_scores(self, uid: int) -> Dict[str, List[int]]:
        """
        获取用户所有车辆的宫殿分数列表。
        返回格式：
        {
            "car_id1": [score1, score2, score3, score4, score5],
            "car_id2": [...],
            ...
        }
        """
        try:
            car_list = self.get_car_list(uid)
            palace_scores = {}
            for car_id, car_data in car_list.items():
                palace_score_list = car_data.get('palace_score_list', [])
                scores = []
                for i in range(5):
                    if i < len(palace_score_list):
                        scores.append(palace_score_list[i].get('score', -1))
                    else:
                        scores.append(-1)
                palace_scores[car_id] = scores
            return palace_scores
        except Exception as e:
            self._handle_db_error("获取宫殿分数", uid, e)
            return {}



def format_rank_list(rank_list: List[Union[Dict[str, Any], int]]) -> str:
    """格式化输出比赛排名列表"""
    if not rank_list:
        return "[]"

    lines = ["["]
    for item in rank_list:
        if isinstance(item, dict):
            lines.append("  {")
            for k, v in sorted(item.items()):
                lines.append(f"    {k}: {v},")
            lines.append("  },")
        else:
            lines.append(f"  {item},")
    lines.append("]")
    return "\n".join(lines)


def parse_uids(uids_str: str = None, file_path: str = None) -> Tuple[List[int], str]:
    """解析UID列表，支持直接输入或文件读取"""
    if file_path:
        try:
            with open(file_path, 'r') as f:
                uids = [int(line.strip()) for line in f if line.strip()]
            return uids, f"从文件 {file_path} 读取"
        except Exception as e:
            print(f"读取UID文件失败: {e}")
            return [], f"读取UID文件失败: {e}"
    elif uids_str:
        try:
            uids = [int(uid.strip()) for uid in uids_str.split(',') if uid.strip()]
            return uids, "从命令行参数读取"
        except Exception as e:
            print(f"解析UID参数失败: {e}")
            return [], f"解析UID参数失败: {e}"
    return [], "无UID输入"


def setup_arg_parser() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(description="MongoDB数据管理工具")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # 查询命令
    query_parser = subparsers.add_parser('query', help='查询数据')
    query_parser.add_argument("--uids", type=int, nargs="+", required=True, help="用户ID列表")
    query_parser.add_argument("--type", choices=["user", "car", "rank-list", "all"],
                              default="all", help="查询类型")

    # 用户排名操作
    update_user_parser = subparsers.add_parser('update-user', help='更新用户排名')
    update_user_parser.add_argument("--uid", type=int, required=True, help="用户ID")
    update_user_parser.add_argument("--score", type=int, required=True, help="新的rank_score")
    update_user_parser.add_argument("--level", type=int, required=True, help="新的rank_level_score")

    # 车辆分数操作
    car_parser = subparsers.add_parser('car', help='车辆分数操作')
    car_subparsers = car_parser.add_subparsers(dest='car_command', required=True)

    update_car = car_subparsers.add_parser('update', help='更新单个用户的车辆分数')
    update_car.add_argument("--uid", type=int, required=True, help="用户ID")
    update_car.add_argument("--car-id", type=str, required=True, help="车辆ID")
    update_car.add_argument("--rank-score", type=int, required=True, help="新的rank_score")
    update_car.add_argument("--season-score", type=int, required=True, help="新的season_best_rank_score")

    batch_update_car = car_subparsers.add_parser('batch-update', help='批量更新多个用户的车辆分数')
    batch_update_car.add_argument("--uids", type=int, nargs="+", required=True, help="用户ID列表")
    batch_update_car.add_argument("--car-id", type=str, required=True, help="车辆ID")
    batch_update_car.add_argument("--rank-score", type=int, required=True, help="新的rank_score")
    batch_update_car.add_argument("--season-score", type=int, required=True, help="新的season_best_rank_score")

    # 新增：批量更新一个用户的多辆车辆
    batch_user_cars = car_subparsers.add_parser('batch-update-user-cars',
                                                help='批量更新一个用户的多辆车辆分数')
    batch_user_cars.add_argument("--uid", type=int, required=True, help="用户ID")
    batch_user_cars.add_argument("--updates", type=json.loads, required=True,
                                 help='更新内容(JSON格式)，如: {"5001":{"rank_score":1000,"season_score":2000},"5002":{"rank_score":1500}}')

    # 比赛记录操作
    rank_parser = subparsers.add_parser('rank-list', help='比赛记录操作')
    rank_subparsers = rank_parser.add_subparsers(dest='rank_command', required=True)

    get_rank = rank_subparsers.add_parser('get', help='获取单个用户的recent_rank_list')
    get_rank.add_argument("--uid", type=int, required=True, help="用户ID")

    batch_get_rank = rank_subparsers.add_parser('batch-get', help='批量获取多个用户的recent_rank_list')
    uid_group = batch_get_rank.add_mutually_exclusive_group(required=True)
    uid_group.add_argument("--uids", type=str, help="逗号分隔的UID列表")
    uid_group.add_argument("--file", type=str, help="包含UID列表的文件路径")

    update_rank_list = rank_subparsers.add_parser('update-list', help='更新整个recent_rank_list')
    update_rank_list.add_argument("--uid", type=int, required=True, help="用户ID")
    update_rank_list.add_argument("--new-list", type=json.loads, required=True,
                                  help='新的列表内容（JSON格式），如 "[{\\"rank\\":1}, 2]"')

    batch_update_rank_list = rank_subparsers.add_parser('batch-update-list',
                                                        help='批量更新多个用户的整个recent_rank_list')
    batch_uid_group = batch_update_rank_list.add_mutually_exclusive_group(required=True)
    batch_uid_group.add_argument("--uids", type=str, help="逗号分隔的UID列表")
    batch_uid_group.add_argument("--file", type=str, help="包含UID列表的文件路径")
    batch_update_rank_list.add_argument("--new-list", type=json.loads, required=True,
                                        help='新的列表内容（JSON格式）')

    update_record = rank_subparsers.add_parser('update-record', help='更新单个记录')
    update_record.add_argument("--uid", type=int, required=True, help="用户ID")
    update_record.add_argument("--index", type=int, required=True, help="记录索引（从0开始）")
    update_record.add_argument("--value", type=json.loads, required=True,
                               help='新值（JSON格式），如 "{\\"rank\\":1}" 或 2')

    batch_update_record = rank_subparsers.add_parser('batch-update-record',
                                                     help='批量更新多个用户的单个记录')
    batch_record_uid_group = batch_update_record.add_mutually_exclusive_group(required=True)
    batch_record_uid_group.add_argument("--uids", type=str, help="逗号分隔的UID列表")
    batch_record_uid_group.add_argument("--file", type=str, help="包含UID列表的文件路径")
    batch_update_record.add_argument("--index", type=int, required=True, help="记录索引")
    batch_update_record.add_argument("--value", type=json.loads, required=True,
                                     help='新值（JSON格式）')

    # 组合更新命令
    combo_parser = subparsers.add_parser('combo-update', help='组合更新车辆分数和比赛记录')
    combo_parser.add_argument("--uids", type=str, required=True, help="逗号分隔的UID列表")
    combo_parser.add_argument("--car-id", type=str, required=True, help="车辆ID")
    combo_parser.add_argument("--rank-score", type=int, required=True, help="新的rank_score")
    combo_parser.add_argument("--season-score", type=int, required=True, help="新的season_best_rank_score")
    combo_parser.add_argument("--rank-list", type=json.loads, required=True,
                              help='新的比赛记录列表（JSON格式），如 "[1,1,3,4,1]"')

    # 更新车辆分数命令
    update_car_score_parser = subparsers.add_parser('update-car-score',
                                                    help='更新单个用户的车辆分数')
    update_car_score_parser.add_argument("--uid", type=int, required=True, help="用户ID")
    update_car_score_parser.add_argument("--car-id", type=str, required=True, help="车辆ID")
    update_car_score_parser.add_argument("--rank-score", type=int, required=True,
                                         help="新的rank_score值")
    update_car_score_parser.add_argument("--season-score", type=int, required=True,
                                         help="新的season_best_rank_score值")

    return parser


def print_result(title: str, result: Any, formatter=None) -> None:
    """统一格式化输出结果"""
    print(f"\n===== {title} =====")
    if formatter and callable(formatter):
        print(formatter(result))
    else:
        pprint.pprint(result)
    print("=" * 50)


def handle_query(args, manager):
    """处理查询命令"""
    for uid in args.uids:
        results = {}
        if args.type in ["user", "all"]:
            results["用户排名"] = manager.get_user_rank(uid)
        if args.type in ["car", "all"]:
            results["车辆分数"] = manager.get_car_scores(uid)
        if args.type in ["rank-list", "all"]:
            results["比赛记录"] = manager.get_recent_rank_list(uid)

        def format_car_scores(data: Dict[str, Dict[str, Any]]) -> str:
            """自定义格式化车辆分数数据"""
            return "{\n" + ",\n".join(
                f'    "{car_id}": {{"rank_score": {scores.get("rank_score", "N/A")}, '
                f'"season_best_rank_score": {scores.get("season_best_rank_score", "N/A")}, '
                f'"palace_score_list": {scores.get("recent_palace_score", [])}}}'
                for car_id, scores in data.items()
            ) + "\n}"

        print_result(f"UID {uid} 查询结果", results, lambda x: "\n".join(
            f"[{k}]:\n{format_rank_list(v) if k == '比赛记录' else format_car_scores(v) if k == '车辆分数' else pprint.pformat(v)}"
            for k, v in x.items() if v
        ))


def main():
    parser = setup_arg_parser()
    args = parser.parse_args()

    manager = MongoDBManager()
    try:
        if not manager.connect():
            return

        if args.command == 'query':
            handle_query(args, manager)

        elif args.command == 'update-user':
            result = manager.update_user_rank(args.uid, args.score, args.level)
            print_result("更新用户排名", result or "更新失败或数据未改变")

        elif args.command == 'car':
            if args.car_command == 'update':
                result = manager.update_car_scores(
                    args.uid, args.car_id, args.rank_score, args.season_score
                )
                print_result("更新车辆分数", result)
            elif args.car_command == 'batch-update':
                results = manager.batch_update_car_scores(
                    args.uids, args.car_id, args.rank_score, args.season_score
                )
                success_count = sum(1 for r in results.values() if r['success'])
                print_result("批量更新车辆分数", {
                    '总计': f"{success_count}/{len(args.uids)}",
                    '详情': results
                })
            elif args.car_command == 'batch-update-user-cars':
                result = manager.update_palace_scores(args.uid, args.updates)
                print_result("批量更新用户车辆", result)

        elif args.command == 'rank-list':
            if args.rank_command == 'get':
                result = manager.get_recent_rank_list(args.uid)
                print_result("获取比赛记录", format_rank_list(result) if result else "获取失败")

            elif args.rank_command == 'batch-get':
                uids, source = parse_uids(getattr(args, 'uids'), getattr(args, 'file'))
                print(f"UID来源: {source}")
                for uid in uids:
                    result = manager.get_recent_rank_list(uid)
                    print_result(f"UID {uid} 比赛记录",
                                 format_rank_list(result) if result else "获取失败")

            elif args.rank_command == 'update-list':
                result = manager.update_recent_rank_list(args.uid, args.new_list)
                print_result("更新比赛记录", result)

            elif args.rank_command == 'batch-update-list':
                uids, source = parse_uids(getattr(args, 'uids'), getattr(args, 'file'))
                print(f"UID来源: {source}")
                results = manager.batch_update_recent_rank_list(uids, args.new_list)
                success_count = sum(1 for r in results.values() if r['success'])
                print_result("批量更新比赛记录", {
                    '总计': f"{success_count}/{len(uids)}",
                    '详情': results
                })

            elif args.rank_command == 'update-record':
                result = manager.update_single_record(args.uid, args.index, args.value)
                print_result("更新比赛记录项", result)

            elif args.rank_command == 'batch-update-record':
                uids, source = parse_uids(getattr(args, 'uids'), getattr(args, 'file'))
                print(f"UID来源: {source}")
                results = manager.batch_update_single_record(uids, args.index, args.value)
                success_count = sum(1 for r in results.values() if r['success'])
                print_result("批量更新比赛记录项", {
                    '总计': f"{success_count}/{len(uids)}",
                    '详情': results
                })

        elif args.command == 'combo-update':
            uids, source = parse_uids(args.uids)
            print(f"\n===== 开始组合更新 =====")
            print(f"UID列表: {uids}")
            print(f"车辆ID: {args.car_id}")
            print(f"Rank Score: {args.rank_score}")
            print(f"Season Score: {args.season_score}")
            print(f"Rank List: {args.rank_list}")
            print("=" * 50)

            results = {}
            for uid in uids:
                print(f"\n处理 UID {uid}:")

                # 初始化操作列表
                operations = []
                update_success = True

                # 检查是否需要更新车辆分数
                if args.car_id and args.rank_score is not None and args.season_score is not None:
                    print("1. 正在更新车辆分数...")
                    car_result = manager.update_car_scores(
                        uid, args.car_id, args.rank_score, args.season_score
                    )
                    operations.append(('车辆', car_result))
                    update_success = update_success and car_result.get('success', False)
                    if car_result.get('success'):
                        print(f"  成功! 更新后数据: {car_result['data']}")
                    else:
                        print(f"  失败! 原因: {car_result.get('error', '未知错误')}")
                else:
                    print("1. 跳过车辆分数更新（参数不全）")

                # 总是更新比赛记录
                print("2. 正在更新比赛记录...")
                rank_result = manager.update_recent_rank_list(uid, args.rank_list)
                operations.append(('比赛记录', rank_result))
                update_success = update_success and rank_result.get('success', False)
                if rank_result.get('success'):
                    print(f"  成功! 更新后记录: {rank_result['data']}")
                else:
                    print(f"  失败! 原因: {rank_result.get('error', '未知错误')}")

                results[uid] = {
                    'operations': operations,
                    'success': update_success
                }

            success_count = sum(1 for r in results.values() if r['success'])
            print("\n===== 组合更新结果汇总 =====")
            print(f"总计: {len(uids)} 个用户")
            print(f"成功: {success_count} 个")
            print(f"失败: {len(uids) - success_count} 个")

            if success_count < len(uids):
                print("\n失败详情:")
                for uid, result in results.items():
                    if not result['success']:
                        print(f"UID {uid}:")
                        for op_name, op_result in result['operations']:
                            if not op_result.get('success'):
                                print(f"  {op_name}更新失败: {op_result.get('error')}")

            print("\n===== 组合更新完成 =====")

        elif args.command == 'update-car-score':
            print(f"\n===== 开始更新车辆分数 =====")
            print(f"UID: {args.uid}")
            print(f"车辆ID: {args.car_id}")
            print(f"Rank Score: {args.rank_score}")
            print(f"Season Score: {args.season_score}")

            result = manager.update_car_scores(
                args.uid, args.car_id, args.rank_score, args.season_score
            )

            if result['success']:
                print("\n===== 更新成功 =====")
                print("更新后数据:")
                manager.pp.pprint(result['data'])
            else:
                print("\n===== 更新失败 =====")
                print(f"错误原因: {result.get('error', '未知错误')}")

            print("\n===== 操作完成 =====")

    finally:
        manager.close()


if __name__ == "__main__":
    main()

"""
 #查询用户排名和车辆分数：
python sc.py query --uids 10001779 --type all

更新用户排名和分数：
python sc.py update-user --uid 10000621 --score 0 --level 0

更新用户的殿堂近5场分数
  python sc.py car batch-update-user-cars \
    --uid 10001779\
    --updates '{
        "10006": {"palace_scores": [0,50,50,50,100]},
        "10001": {"palace_scores": [0,0,50,50,90]}
    }'


修改车辆的分数和赛季分数
python sc.py car batch-update-user-cars \
    --uid 10000444 \
    --updates '{
      "10001": {"rank_score": 210, "season_best_rank_score": 210}
}
'


修改车辆排位分和殿堂分
python sc.py car batch-update-user-cars \
    --uid 10000560 \
    --updates '{
        "10001": {
            "palace_scores": [50,50,50,50,150],
            "rank_score": 1550
        }
    }'


# 修改比赛排名
python sc.py rank-list batch-update-list \
    --uids "10000444" \
    --new-list "[1,1,1,1,1]"

"""