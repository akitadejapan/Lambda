"""
概要
    S3にアップロードされた画像をリサイズして別のS3バケットに保存するLambda関数
参照URL
    ベースはこれを参照：https://zenn.dev/cocomina/articles/lambda-image-resize
    PILのダウンロード：https://qiita.com/PDC-Kurashinak/items/8df68b5260646b9611f9
    環境変数の設定：https://qiita.com/N_H_tennis/items/b30ed6370ccf959407f5
    オブジェクト名の文字化け対策：https://dev.classmethod.jp/articles/tsnote-s3-eventnotifications-lambda-decode/
    その他：
        https://qiita.com/kurono/items/237c3552dd437838dbc9
"""



import boto3
import os
from PIL import Image
import io
import urllib.parse

s3_client = boto3.client('s3')
TARGET_BUCKET = os.environ['TARGET_BUCKET']
TARGET_PREFIX = os.environ['TARGET_PREFIX']

def resize_image(image_bytes, width):
    #PILでイメージを開く
    image = Image.open(io.BytesIO(image_bytes))

    #アスペクト比を計算
    aspect_ratio = image.height / image.width
    new_height = int(width * aspect_ratio)
    
    #リサイズ実行
    resized_image = image.resize((width, new_height),Image.Resampling.LANCZOS)

    #バッファに保存
    buffer = io.BytesIO()
    #元の形式を保持
    format = image.format if image.format else 'JPEG'
    resized_image.save(buffer, format=format, quality=85)
    buffer.seek(0)

    return buffer.getvalue()

def lambda_handler(event, context):
    try:
        #S3イベントから情報を取得
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'],encoding='utf-8')
        print(key)

        #contensフォルダ内の画像のみ処理
        if not key.startswith('contents/'):
            return{
                'statusCode': 200,
                'body': 'Skipped: Not a target image'
            }
        
        #リサイズ済み画像はスキップ  
        if '-m.' in key or '-s.' in key:
            return{
                'statusCode': 200,
                'body': 'Skipped: Already resized image'
            }


        #対象の拡張子をチェック  
        if not key.lower().endswith(('.jpg','.jpeg','.png','.webp')):
            return{
                'statusCode': 200,
                'body': 'Skipped: Not a supported image format'
            }
        
        #元画像を取得
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_bytes = response['Body'].read()
        # print(image_bytes)

        #ファイル名とパスを分離
        # directory = os.path.dirname(key)
        filename = os.path.basename(key)
        name, ext = os.path.splitext(filename)

        #Mサイズ(600px)を作成
        m_image = resize_image(image_bytes,600)
        m_filename = f"{name}-m{ext}"
        m_key =f"{TARGET_PREFIX}/{m_filename}"
        response = s3_client.put_object(
            Bucket=TARGET_BUCKET,
            Key=m_key,
            Body=m_image
        )
        # print(response)

        #Sサイズ(240px)を作成
        s_image = resize_image(image_bytes,240)
        s_filename = f"{name}-s{ext}"
        s_key = f"{TARGET_PREFIX}/{s_filename}"
        s3_client.put_object(
            Bucket=TARGET_BUCKET,
            Key=s_key,
            Body=s_image
        )

        return{
            'statusCode': 200,
            'body': 'Successfully resized image'
        }
    except Exception as e:
        print(f'Error: {str(e)}')
        raise e
