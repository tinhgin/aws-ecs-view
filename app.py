from flask import Flask, render_template
import boto3
import os
import datetime
import time

app = Flask(__name__)
client = boto3.client('ecs')
logs_client = boto3.client('logs')
cluster = os.getenv('ECS_CLUSTER')


@app.template_filter('ctime')
def timectime(s):
    return datetime.datetime.fromtimestamp(s / 1e3)


def get_tasks():
    running_tasks = client.list_tasks(
        cluster=cluster,
        desiredStatus='RUNNING'
    )['taskArns']
    pending_tasks = client.list_tasks(
        cluster=cluster,
        desiredStatus='PENDING'
    )['taskArns']
    stopped_tasks = client.list_tasks(
        cluster=cluster,
        desiredStatus='STOPPED'
    )['taskArns']
    tasks = running_tasks + pending_tasks + stopped_tasks
    tasks_detail = client.describe_tasks(
        cluster=cluster,
        tasks=tasks,
    )
    return tasks_detail['tasks']


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/cluster')
def cluster_detail():
    return render_template('cluster.html')


@app.route('/service')
def service():
    return render_template('service.html')


@app.route('/task')
def task_list():
    return render_template('task.html', tasks=get_tasks())


@app.route('/task/<string:task_id>/log')
def task_log(task_id):
    try:
        task = client.describe_tasks(cluster=cluster, tasks=[task_id])['tasks'][0]
        status = task['containers'][0]['lastStatus']
        task_def = task['taskDefinitionArn'].split("/")[-1]
        docker_tag = task['containers'][0]['image'].split("/")[-1].split(":")[-1]

        task_def_des = client.describe_task_definition(taskDefinition=task_def)
        log_group_name = task_def_des['taskDefinition']['containerDefinitions'][0]['logConfiguration']['options'][
            'awslogs-group']
        task_family = task_def_des['taskDefinition']['family']
        container_name = task_def_des['taskDefinition']['containerDefinitions'][0]['name']
        log_stream_name = task_family + "/" + container_name + "/" + task_id

        now = round(time.time() * 1000)
        log_events = logs_client.get_log_events(
            logGroupName=log_group_name,
            logStreamName=log_stream_name,
            startTime=(now-3600000),
            endTime=now,
            startFromHead=True
        )['events']
    except Exception as e:
        print(e)

    return render_template('log.html', id=task_id, status=status, task_def=task_def, docker_tag=docker_tag,
                           log_events=log_events)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
