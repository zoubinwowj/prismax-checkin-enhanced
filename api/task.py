#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function for task status (simplified)
"""

import json
from datetime import datetime

def handler(request):
    """Vercel serverless function handler"""
    
    # 处理CORS
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        }
    
    if request.method != 'GET':
        return {
            'statusCode': 405,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'success': False, 'message': 'Method not allowed'})
        }
    
    try:
        # 从URL路径获取task_id
        path = request.url.path if hasattr(request.url, 'path') else request.path
        task_id = path.split('/')[-1]
        
        # 返回模拟的已完成任务状态
        task_data = {
            'id': task_id,
            'status': 'completed',
            'stats': {
                'total': 0,
                'success': 0,
                'already': 0,
                'failed': 0,
                'points': 0
            },
            'current_round': 1,
            'wallet_count': 0,
            'created_time': datetime.now().isoformat(),
            'logs': [
                {
                    'time': datetime.now().isoformat(),
                    'message': '任务已在前端完成处理'
                }
            ]
        }
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'task': task_data
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
