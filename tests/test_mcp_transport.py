import json
import unittest
from unittest.mock import patch
import httpx
from fast_api.app.tools.mcp_client import MCPClient


class MCPTransportTests(unittest.IsolatedAsyncioTestCase):
    async def exercise_transport(self,sse=False):
        seen=[]
        def handle(request):
            if request.method=='DELETE':return httpx.Response(204)
            body=json.loads(request.content);seen.append(body['method'])
            method=body['method']
            if method=='notifications/initialized':return httpx.Response(202)
            result={'protocolVersion':'2025-03-26'} if method=='initialize' else {'tools':[{'name':'search_exercises'}]} if method=='tools/list' else {'structuredContent':{'results':[]}}
            message={'jsonrpc':'2.0','id':body['id'],'result':result}
            headers={'Mcp-Session-Id':'test-session'} if method=='initialize' else {}
            if method!='initialize':self.assertEqual(request.headers['Mcp-Session-Id'],'test-session')
            if sse:
                headers['content-type']='text/event-stream'
                return httpx.Response(200,headers=headers,text='data: '+json.dumps(message)+'\n\n')
            return httpx.Response(200,headers=headers,json=message)
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch('fast_api.app.tools.mcp_client.httpx.AsyncClient',return_value=client):
            result=await MCPClient('https://example.invalid/mcp').call_tool('search_exercises',{})
        self.assertEqual(result,{'structuredContent':{'results':[]}})
        self.assertEqual(seen,['initialize','notifications/initialized','tools/list','tools/call'])

    async def test_json(self):await self.exercise_transport()
    async def test_sse(self):await self.exercise_transport(True)
