import aiohttp
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star
from astrbot.api import logger
from astrbot.api import AstrBotConfig

class GlmQuotaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    @filter.llm_tool(name="query_glm_quota")
    async def check_quota(self, event: AstrMessageEvent) -> MessageEventResult:
        '''查询智谱AI (GLM) 账号的余额和用量配额限制。当用户询问 GLM 余额、额度时调用此工具。'''
        
        api_key = self.config.get("api_key", "")
        if not api_key:
            yield event.plain_result("请先在插件配置中填写 API Key")
            return
            
        url = "https://open.bigmodel.cn/api/monitor/usage/quota/limit"
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    logger.info(f"[Debug] GLM API Response: {data}")
                    
                    if not data.get("success"):
                        yield event.plain_result(f"查询失败: {data.get('msg', '未知错误')}")
                        return

                    limits = data.get("data", {}).get("limits", [])
                    now = datetime.now()
                    result = ["📊 GLM Coding Plan 用量："]

                    for item in limits:
                        unit = item.get("unit", 0)
                        number = item.get("number", 0)
                        percentage = item.get("percentage", 0)
                        
                        if item["type"] == "TOKENS_LIMIT":
                            unit_map = {3: "小时", 4: "天", 5: "周", 6: "周"}
                            unit_str = unit_map.get(unit, f"单位{unit}")
                            name = f"{number}{unit_str}额度"
                            status = f"已用 {percentage}%，剩余 {100 - percentage}%"
                        elif item["type"] == "TIME_LIMIT":
                            unit_map = {5: "月"}
                            unit_str = unit_map.get(unit, "")
                            name = f"MCP额度 ({number}{unit_str})"
                            status = f"已用 {item.get('currentValue', 0)} 次，剩余 {item.get('remaining', 0)} 次 (总额 {item.get('usage', 0)} 次)"
                        else:
                            name = item["type"]
                            status = f"已用 {percentage}%"

                        reset_ts = item.get("nextResetTime", 0)
                        if reset_ts and reset_ts > 0:
                            reset_time = datetime.fromtimestamp(reset_ts / 1000)
                            diff = reset_time - now
                            if diff.total_seconds() > 0:
                                hours, remainder = divmod(int(diff.total_seconds()), 3600)
                                minutes, seconds = divmod(remainder, 60)
                                countdown = f"{hours}小时{minutes}分{seconds}秒"
                                status += f" (重置倒计时: {countdown})"

                        result.append(f"🔹 {name}: {status}")
                    
                    yield event.plain_result("\n".join(result))
                    
        except Exception as e:
            yield event.plain_result(f"请求异常: {str(e)}")
