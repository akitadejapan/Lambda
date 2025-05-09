import os
import boto3
import base64
import logging
from datetime import datetime, timedelta
import time
import botocore

# ロギングの設定
t_logger = logging.getLogger()
t_logger.setLevel(logging.INFO)

# boto3のクライアントを作成
s3 = boto3.client('s3')
iam = boto3.client('iam')

# 環境変数からS3バケット名を取得
S3_BUCKET = os.environ.get('S3_BUCKET')

def lambda_handler(event, context):
    """
    AWS Lambda を利用してIAM認証情報レポートを取得して、S3に保存する関数。

    環境変数:
      - S3_BUCKET: ターゲットのS3バケット名
    """
    # 1. 認証情報レポートを生成
    try:
        resp = iam.generate_credential_report()
        t_logger.info(f"Credential report generation initiated: {resp['State']}")
    except Exception as e:
        t_logger.error(f"Failed to generate credential report: {e}")
        raise

    # 2.認証情報レポートが取得できるまで5秒間隔で最大10回までリトライ
    MAX_ATTEMPTS = 10
    DELAY_SECONDS = 5
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            report = iam.get_credential_report()
            # 成功したらループを抜ける
            break
        except botocore.exceptions.ClientError as e:
            code = e.response['Error']['Code']
            if code == 'ReportNotPresent':
                logging.info(f"Credential report not ready yet (attempt {attempt}/{MAX_ATTEMPTS})_error: {e}")
                time.sleep(DELAY_SECONDS)
            else:
                # その他のエラーは再送せず例外として上げる
                raise
    else:
        raise TimeoutError("IAM credential report was not generated within the expected time frame.")


    # 3. 認証情報レポートを取得
    try:
        report = iam.get_credential_report()
    except Exception as e:
        t_logger.error(f"Failed to retrieve credential report: {e}")
        raise

    # 4. ファイル名を生成
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    # Convert to Japan Standard Time (JST)
    jst_timestamp = datetime.strptime(timestamp, '%Y%m%d_%H%M%S') + timedelta(hours=9)
    key = f"credential_report_{jst_timestamp}.csv"

    # 5. S3にアップロード
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key="iam-credential-reports/" + key,
            Body=report['Content'],
            ContentType='text/csv; charset=utf-8'
        )
        t_logger.info(f"Uploaded report to s3://{S3_BUCKET}/iam-credential-reports/{key}")
    except Exception as e:
        t_logger.error(f"Failed to upload report to S3: {e}")
        raise

    return {
        'statusCode': 200,
        'body': f"IAM credential report saved to s3://{S3_BUCKET}/iam-credential-reports/{key}"
    }
