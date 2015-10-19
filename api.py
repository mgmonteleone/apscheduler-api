from flask import Flask
from flask import render_template

from flask_restful import reqparse, abort, fields, marshal_with, Api, Resource

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from flask_restful import Resource, fields, marshal_with

import atexit

app = Flask(__name__)
api = Api(app)

# Fields that are expected and need to be exposed from a Job
fields = {
    'id': fields.String(),
    'name': fields.String(),
    'task_class': fields.String(attribute=lambda x: x.func_ref.replace(':', '.').replace('.execute', '')),
    'next_run_time': fields.DateTime(dt_format='iso8601'),
    'misfire_grace_time': fields.String(),
    'coalesce': fields.Boolean(),
    'trigger': fields.String(),
    'args': fields.List(fields.String),
    'start_date': fields.DateTime(attribute=lambda x: x.trigger.start_date, dt_format='iso8601'),
    'end_date': fields.DateTime(attribute=lambda x: x.trigger.end_date, dt_format='iso8601'),
    'timezone': fields.String(),
    'year': fields.String(attribute=lambda x: x.trigger.fields[0] if not x.trigger.fields[0].is_default else None),
    'month': fields.String(attribute=lambda x: x.trigger.fields[1] if not x.trigger.fields[1].is_default else None ),
    'day': fields.String(attribute=lambda x: x.trigger.fields[2] if not x.trigger.fields[2].is_default else None ),
    'week': fields.String(attribute=lambda x: x.trigger.fields[3] if not x.trigger.fields[3].is_default else None ),
    'day_of_week': fields.String(attribute=lambda x: x.trigger.fields[4] if not x.trigger.fields[4].is_default else None ),
    'hour': fields.String(attribute=lambda x: x.trigger.fields[5] if not x.trigger.fields[5].is_default else None ),
    'minute': fields.String(attribute=lambda x: x.trigger.fields[6] if not x.trigger.fields[6].is_default else None ),
    'second': fields.String(attribute=lambda x: x.trigger.fields[7] if not x.trigger.fields[7].is_default else None ),
}

jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite3')
}
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

def job_listener(event):
    if event.exception:
        print('The job crashed :(')
    else:
        print('The job worked :)')

scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

def abort_if_job_doesnt_exist(job_id):
    if None == scheduler.get_job(job_id):
        abort(404, message="Job {} doesn't exist".format(job_id))

def shutdown():
    scheduler.shutdown()

def my_import(name):
    components = name.split('.')
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


atexit.register(shutdown)

parser = reqparse.RequestParser()
parser.add_argument('name', required=True, help="Name is required")
parser.add_argument('task_class', required=True, help="Task Class is required")

parser.add_argument('minute', type=int)
parser.add_argument('hour', type=int)
parser.add_argument('day', type=int)
parser.add_argument('month', type=int)
parser.add_argument('day_of_week')
parser.add_argument('start_date')
parser.add_argument('end_date')

parser.add_argument('misfire_grace_time')
parser.add_argument('coalesce', type=bool)

parser.add_argument('args', action='append')
parser.add_argument('active')

# Job
# shows a single Job and lets you delete a todo item
class Job(Resource):
    @marshal_with(fields)
    def get(self, job_id):
        abort_if_job_doesnt_exist(job_id)
        return scheduler.get_job(job_id)

    def delete(self, job_id):
        abort_if_job_doesnt_exist(job_id)
        scheduler.remove_job(job_id)
        return '', 204

    @marshal_with(fields)
    def put(self, job_id):
        args = parser.parse_args()

        klass = my_import(args['task_class'])
        func = getattr(klass, 'execute')

        # TODO: really parse AND VALIDATE the args here or this could get dangerous
        job = scheduler.add_job(
            func,
            'cron',
            id=job_id,
            name=args['name'],
            args=args['args'],
            start_date=args['start_date'],
            end_date=args['end_date'],
            minute=args['minute'],
            hour=args['hour'],
            day=args['day'],
            month=args['month'],
            day_of_week=args['day_of_week'],
            replace_existing=True
        )
        return job, 200


# JobList shows a list of all jobs, and lets you POST to add a new one
class JobList(Resource):
    @marshal_with(fields)
    def get(self):
        return scheduler.get_jobs()

    @marshal_with(fields)
    def post(self):
        args = parser.parse_args()

        klass = my_import(args['task_class'])
        func = getattr(klass, 'execute')

        # TODO: really parse AND VALIDATE the args here or this could get dangerous
        job = scheduler.add_job(
            func,
            'cron',
            name=args['name'],
            args=args['args'],
            start_date=args['start_date'],
            end_date=args['end_date'],
            minute=args['minute'],
            hour=args['hour'],
            day=args['day'],
            month=args['month'],
            day_of_week=args['day_of_week'],
            replace_existing=True
        )
        return job, 201

##
## Actually setup the Api resource routing here
##
api.add_resource(JobList, '/jobs')
api.add_resource(Job, '/jobs/<job_id>')

@app.route("/")
@app.route("/<theme>")
def index(theme=None):
    return render_template('index.html', theme=theme)

if __name__ == '__main__':
    app.run(debug=True)
