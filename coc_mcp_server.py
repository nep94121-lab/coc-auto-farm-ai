import os
import sys
import json
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coc_executor_tools import (
    get_status,
    find_rich_target,
    execute_attack_plan,
    prepare_village_wall_grid,
    upgrade_walls_batch,
)

TOOLS_SCHEMA = [
    {
        "name": "coc_get_status",
        "description": "Chụp màn hình điện thoại kèm lưới tọa độ (x,y) và trả về trạng thái game (home_village / battle_scout / battle_active) cùng số Vàng & Tiên dược.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "with_grid": {"type": "boolean", "default": True}
            },
        },
    },
    {
        "name": "coc_find_rich_target",
        "description": "Tự bấm tìm trận và bấm Next lọc nhà có Vàng >= min_gold VÀ Tiên dược >= min_elixir (tách riêng từng loại). Khi thấy nhà đạt chuẩn sẽ xuất ảnh kẻ lưới tọa độ target_grid.png để AI chọn tọa độ thả quân.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_gold": {"type": "integer", "default": 1000000},
                "min_elixir": {"type": "integer", "default": 1000000},
                "max_searches": {"type": "integer", "default": 60},
            },
        },
    },
    {
        "name": "coc_execute_attack_plan",
        "description": "Thực thi rải 8 Super Yeti, 2 Super Wall Breaker, 3 Clone Spell, 1 Rage Spell theo đúng danh sách tọa độ [[x,y], ...] do AI Planner chỉ điểm, tự canh thắng trận và về làng.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "yeti_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                },
                "wb_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                },
                "clone_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                },
                "rage_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                },
                "wait_finish": {"type": "boolean", "default": True},
            },
            "required": ["yeti_points", "wb_points", "clone_points", "rage_points"],
        },
    },
    {
        "name": "coc_prepare_village_wall_grid",
        "description": "Thu nhỏ Làng chính tối đa, khóa camera sát mép trên (Top-Stop) và chụp ảnh kẻ lưới tọa độ village_grid.png để AI chỉ điểm tọa độ các viên Tường cần nâng.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "coc_upgrade_walls_batch",
        "description": "Nâng Tường 1 thể (Multi-Wall +1) bằng Vàng và Tiên dược tại danh sách tọa độ Tường [[wx,wy], ...] do AI chỉ điểm.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "wall_points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                },
                "use_gold": {"type": "boolean", "default": True},
                "use_elixir": {"type": "boolean", "default": True},
            },
            "required": ["wall_points"],
        },
    },
]


def _call_tool(name, args):
    args = args or {}
    if name == "coc_get_status":
        return get_status(with_grid=bool(args.get("with_grid", True)))
    if name == "coc_find_rich_target":
        return find_rich_target(
            min_gold=int(args.get("min_gold", 1000000)),
            min_elixir=int(args.get("min_elixir", 1000000)),
            max_searches=int(args.get("max_searches", 60)),
        )
    if name == "coc_execute_attack_plan":
        return execute_attack_plan(
            yeti_points=[(int(p[0]), int(p[1])) for p in args["yeti_points"]],
            wb_points=[(int(p[0]), int(p[1])) for p in args["wb_points"]],
            clone_points=[(int(p[0]), int(p[1])) for p in args["clone_points"]],
            rage_points=[(int(p[0]), int(p[1])) for p in args["rage_points"]],
            wait_finish=bool(args.get("wait_finish", True)),
        )
    if name == "coc_prepare_village_wall_grid":
        return prepare_village_wall_grid()
    if name == "coc_upgrade_walls_batch":
        return upgrade_walls_batch(
            wall_points=[(int(p[0]), int(p[1])) for p in args["wall_points"]],
            use_gold=bool(args.get("use_gold", True)),
            use_elixir=bool(args.get("use_elixir", True)),
        )
    raise ValueError(f"Unknown tool: {name}")


def _handle_request(msg):
    method = msg.get("method")
    req_id = msg.get("id")

    if method == "initialize":
        protocol = msg.get("params", {}).get("protocolVersion", "2024-11-05")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": protocol,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "coc-game-executor", "version": "2.0.0"},
            },
        }

    if method in ("notifications/initialized", "notifications/cancelled"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS_SCHEMA}}

    if method == "tools/call":
        params = msg.get("params", {})
        t_name = params.get("name")
        t_args = params.get("arguments", {})
        try:
            res = _call_tool(t_name, t_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}],
                    "isError": not bool(res.get("ok", True)),
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"ok": False, "error": str(exc), "trace": traceback.format_exc()},
                                ensure_ascii=False,
                            ),
                        }
                    ],
                    "isError": True,
                },
            }

    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def main():
    # Hỗ trợ chuẩn MCP stdio newline-delimited JSON-RPC 2.0
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line or line.startswith("Content-Length:"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle_request(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
