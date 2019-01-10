from __future__ import print_function

import boto3
import io
import os
import sys
import datetime
import uuid
import urllib
from PIL import Image, ImageDraw, ImageEnhance
from decimal import Decimal
import json
from pprint import pprint


def lambda_handler(event, context):
    rekognition = boto3.client('rekognition')
    s3 = boto3.client('s3')
    s83 = boto3.resource('s3')
    dynamodb = boto3.client('dynamodb')
    bucket= 'mausamus'
    i = datetime.datetime.now()
    ptr= i.strftime("%d-%m-%y     %H:%M:%S (UTC)")              #string to print date

    if event:
        # print("Event: ", event)
        file_obj = event['Records'][0]
        filename = str(file_obj['s3']['object']['key'])
        print("FileName: ",filename)

        file = filename[7:]
        
        local = '/tmp/'+ptr+'.jpeg'
        out='/tmp/outfile'+ptr+'.jpeg'

        s3.download_file(bucket,filename, local)     #temporary storage  for lambda
        image = Image.open(local)

        stream = io.BytesIO()
        image.save(stream,format="JPEG")
        image_binary = stream.getvalue()


        response = rekognition.detect_text(
            Image={'Bytes':image_binary}
            )

        textDetections = response['TextDetections']

        print('TextDetections: ',textDetections)

        X, Y = image.size
        altered_img = Image.open(local)
        draw = ImageDraw.Draw(altered_img)

        stops = ['TABLETS','CAPSULES','Tablets','Capsules','tablets','capsules','medical','MEDICAL','Medical','mg','MG','10','250','500','650','1000']
        area = []
        for text in textDetections:
            if(text['Type']=='WORD'):
                box=text['Geometry']['BoundingBox']
                mx1 = int(box['Left'] * X)
                my1 = int(box['Top'] * Y)
                mx2 = int(box['Left'] * X + box['Width'] * X)
                my2 = int(box['Top'] * Y + box['Height']  * Y)
                draw.rectangle(((mx1,my1,mx2,my2)), fill=None, outline="blue")
                draw.rectangle(((mx1+1,my1+1,mx2-1,my2-1)), fill=None, outline="blue")
            if len(text['DetectedText'].split(' ')) <= 2:
                h = text['Geometry']['BoundingBox']['Height'] * Y
                w = text['Geometry']['BoundingBox']['Width'] * X
                if len(set(stops).intersection(text['DetectedText'].split(' ')))==0:
                    area.append([text['DetectedText'],h*w])

        area = sorted(area, key=lambda x: x[1])
        result = [area[-1][0],area[-2][0],area[-3][0]]
        print(result)

        counter=0

        if(result):
            for x in result:
                res = dynamodb.get_item(
                    TableName='medicine',
                    Key={'name': {'S': x.upper()}}
                    )
                print('resget:=>',res)
                if('Item' in res):
                    print(res['Item'])
                    rp = dynamodb.put_item(
                        TableName='reso',
                        Item={
                        'result': {'S': file},
                        'Substitute':{'M': res['Item']},
                        'Status':{'S':'yes'}
                        })
                    counter+=1
                    print('rp =>',rp)
                    ktr=filename.replace('upload','download')
                    
                    altered_img.save(out, "JPEG")
                    s3.upload_file(out, 'mausamus', ktr,ExtraArgs={'ContentType': 'image/jpeg','ACL': 'public-read'})
                    break;
                else:
                    print("inside else")
                    continue;

        if(counter==0):
            rp1 = dynamodb.put_item(
                TableName='reso',
                Item={
                'result': {'S': 'hold'},
                'Status':{'S': 'no'}
                })
            print('rp1=>',rp1)