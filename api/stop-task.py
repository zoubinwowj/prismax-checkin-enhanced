#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function for stopping task (simplified)
"""

import json

def handler(request):
    """Vercel serverless function handler"""
    
    # 处理CORS
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        }
    
    if request.method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'success': False, 'message': 'Method not allowed'})
        }
    
    try:
        # 从URL路径获取task_id
        path = request.url.path if hasattr(request.url, 'path') else request.path
        task_id = path.split('/')[-1]
        
        # 返回成功停止的响应
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'message': '任务已停止'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'success': False, 'message': str(e)})
        }

# Vercel入口点
def main(request):
    return handler(request)
