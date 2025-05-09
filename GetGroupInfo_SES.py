import boto3
import re
import time
import datetime
import os
import csv


from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


AWS_S3_BUCKET_NAME = os.environ["AWS_S3_BUCKET_NAME"]
ACCOUNT_ID = os.environ["ACCOUNT_ID"]
SENDER = os.environ["SENDER"]
RECIPIENT = os.environ["RECIPIENT"]

AWS_REGION = "us-east-1"

SUBJECT = "IAMグループ情報_{}".format(datetime.datetime.today())

# The character encoding for the email.
CHARSET = "utf-8"
# The email body for recipients with non-HTML email clients.
BODY_TEXT = "IAMグループ情報\n作成日時：{}".format(datetime.datetime.today())
# The HTML body of the email.
t_delta = datetime.timedelta(hours=9)  # 9時間
JST = datetime.timezone(t_delta, 'JST')  # UTCから9時間差の「JST」タイムゾーン

BODY_HTML = """\
<html>
<head></head>
<body>
<p>今月のIAMグループリスト</p>
<p>アカウントID：{}</p>
<p>作成日時：{}</p>
<p>ファイル格納先：{}</p>
</body>
</html>
""".format(ACCOUNT_ID, datetime.datetime.now(JST), AWS_S3_BUCKET_NAME)


def lambda_handler(event, context):
    # 認証情報レポートを生成
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
            #print('今から「' + group_name + '」の所属ユーザを発表')
            users = iam.get_group(GroupName=group_name)['Users']
            
            for user in users:
                csv_writer.writerow([group_name, user['UserName']])
                #print(user['UserName'])
                
    # 一時ファイルの内容を読み込む
    with open(temp_file_path, 'r') as csvfile:
        csv_content = csvfile.read()
        print(csv_content)
        
    # S3にアップロード
    now_time = datetime.datetime.now(JST)
    fname = now_time.strftime('%Y%m%d_%H%M%S') + "_users.csv"
    ATTACHMENT = "/tmp/" + fname
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(AWS_S3_BUCKET_NAME)
    bucket.put_object(Key='iam/'+ fname, Body=csv_content)
  
 
 
    # メール配信
    # Create a new SES resource and specify a region.
    ses = boto3.client('ses', region_name=AWS_REGION)

    # Create a multipart/mixed parent container.
    msg = MIMEMultipart('mixed')

    # Add subject, from and to lines.
    msg['Subject'] = SUBJECT
    msg['From'] = SENDER
    msg['To'] = RECIPIENT

    # Create a multipart/alternative child container.
    msg_body = MIMEMultipart('alternative')

    # Encode the text and HTML content and set the character encoding. This step is
    # necessary if you're sending a message with characters outside the ASCII range.
    textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)
    htmlpart = MIMEText(BODY_HTML.encode(CHARSET), 'html', CHARSET)

    # Add the text and HTML parts to the child container.
    msg_body.attach(textpart)
    msg_body.attach(htmlpart)

    # Define the attachment part and encode it using MIMEApplication.
    att = MIMEApplication(csv_content)

    # Add a header to tell the email client to treat this part as an attachment,
    # and to give the attachment a name.
    att.add_header('Content-Disposition', 'attachment', filename=os.path.basename(ATTACHMENT))

    # Attach the multipart/alternative child container to the multipart/mixed
    # parent container.
    msg.attach(msg_body)

    # Add the attachment to the parent container.
    msg.attach(att)

    try:
        # Provide the contents of the email.
        response = ses.send_raw_email(
            Source=SENDER,
            Destinations=[
                RECIPIENT
            ],
            RawMessage={
                'Data': msg.as_string(),
            },
            # ConfigurationSetName=CONFIGURATION_SET
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response)
        print(e.response['Error']['Message'])
    else:
        print("Email sent!"),
    return (response['ResponseMetadata']['RequestId'])