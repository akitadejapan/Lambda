import boto3
import re
import time
import datetime
import os
import csv

AWS_S3_BUCKET_NAME = os.environ["AWS_S3_BUCKET_NAME"]
ACCOUNT_ID = os.environ["ACCOUNT_ID"]

def lambda_handler(event, context):

    iam = boto3.client('iam')
    # IAMグループのリストを取得
    groups = iam.list_groups()['Groups']
    print(groups)
    
    # 一時ファイルのパスを設定
    temp_file_path = '/tmp/users.csv'
    with open(temp_file_path, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
    
        # CSVヘッダーを作成
        csv_writer.writerow(['GroupName', 'UserName'])

        # 各グループのユーザーを取得
        for group in groups:
            group_name = group['GroupName']
            users = iam.get_group(GroupName=group_name)['Users']
            
            for user in users:
                csv_writer.writerow([group_name, user['UserName']])
                
    # 一時ファイルの内容を読み込む
    with open(temp_file_path, 'r') as csvfile:
        csv_content = csvfile.read()
        
    # S3にアップロード
    now_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    fname = now_time.strftime('%Y%m%d_%H%M%S') + "_user_list.csv"
    # ATTACHMENT = "/tmp/" + fname
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(AWS_S3_BUCKET_NAME)
    bucket.put_object(Key='iam/'+ fname, Body=csv_content)
  