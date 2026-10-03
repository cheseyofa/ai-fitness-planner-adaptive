import asyncio
import json
import httpx


class MCPClient:
    """Read-only Streamable HTTP client; supports JSON and SSE responses."""
    def __init__(self, url: str, token: str = ""):
        self.url, self.token = url, token

    async def call_tool(self, name: str, arguments: dict) -> dict:
        if not self.url:
            raise ValueError("未配置动作工具服务")
        async with asyncio.timeout(15):
            async with httpx.AsyncClient(timeout=10) as client:
                headers={"Accept":"application/json, text/event-stream"}
                if self.token: headers["Authorization"]="Bearer "+self.token
                async def request(method: str, params: dict, number: int | None) -> dict:
                    body={"jsonrpc":"2.0","method":method,"params":params}
                    if number is not None: body["id"]=number
                    async with client.stream("POST",self.url,json=body,headers=headers) as response:
                        response.raise_for_status()
                        if response.headers.get("mcp-session-id"):
                            headers["Mcp-Session-Id"]=response.headers["mcp-session-id"]
                        if number is None: return {}
                        if "text/event-stream" in response.headers.get("content-type",""):
                            parts=[]
                            async for line in response.aiter_lines():
                                if line.startswith("data:"): parts.append(line[5:].strip())
                                elif not line and parts:
                                    message=json.loads("\n".join(parts));parts=[]
                                    if message.get("id")==number: break
                            else: raise ValueError("工具未返回结果")
                        else: message=json.loads(await response.aread())
                        if message.get("id") != number or "error" in message:
                            raise ValueError("工具调用失败")
                        return message["result"]
                initialized=await request("initialize",{"protocolVersion":"2025-03-26","capabilities":{},
                    "clientInfo":{"name":"fitness-planner","version":"1.0"}},1)
                headers["MCP-Protocol-Version"]=initialized.get("protocolVersion","2025-03-26")
                try:
                    await request("notifications/initialized",{},None)
                    tools=await request("tools/list",{},2)
                    if name not in {t["name"] for t in tools.get("tools",[])}:
                        raise ValueError("服务未提供配置的动作搜索工具")
                    result=await request("tools/call",{"name":name,"arguments":arguments},3)
                    if result.get("isError"): raise ValueError("动作工具返回错误")
                    return result
                finally:
                    if "Mcp-Session-Id" in headers:
                        try: await client.delete(self.url,headers=headers)
                        except httpx.HTTPError: pass
