import lancedb
import json
import openai
from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd

openai.api_key = "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"

#TODO - newrelic stuff since this is in python?
# import os
# os.environ["NEW_RELIC_LICENSE_KEY"] = "bce3af8473051217f786397906e6cbe4c63eNRAL"
# from nr_openai_observability import monitor
# monitor.initialization()

uri = './tmp/lancedb'
db = lancedb.connect(uri)
try:
    action_table = db.create_table('actions')
except:
    action_table = db.open_table('actions')
try:
    task_table = db.create_table('tasks', data=[{'vector': [0] * 1536, 'actions': [{}]}])
except:
    task_table = db.open_table('tasks')

current_actions = {}


app = FastAPI()

@app.post("/{event_name}")
async def action(event_name: str, event: dict):
    if 'session' in event:
        session = event['session']
        saved_event = { **event, 'event_name': event_name }
        if session in current_actions:
            current_actions[session].append(saved_event)
        else:
            current_actions[session] = [saved_event]
        
        # action_table.add({
        #     'vector': vectorize_action(saved_event),
        #     **saved_event,
        # })

        if event_name == 'FinishTask': #the event that will be vectorized will always have the longest history bc of this
            task_vector = vectorize_task(current_actions[session])
            
            task_table.add([{
                'vector': task_vector,
                # TODO: only pass unique identifier here for standard schema
                'actions': current_actions[session],
            }])
            del current_actions[session]

    return {"message": "Hello World"}


@app.get("/")
async def get_task(query: str, limit: int = 10):
    query_embedding = openai.Embedding.create(input=[query], engine='text-embedding-ada-002')['data'][0]['embedding']
    top_tasks = task_table.search(query_embedding).limit(limit)
    top_tasks = top_tasks.to_df()

    return top_tasks.to_string()

def vectorize_task(task):
    finish_task_event = tuple(filter(lambda x: x['event_name'] == 'FinishTask', task))[0]
    history = finish_task_event['prompt'].split('Current time:')
    history[0] = history[0].strip() + '\n'
    history[1] = '\n\nCurrent time:' + history[1]
    history.insert(1, finish_task_event['response'])

    history = '\n'.join(history)
    
    return openai.Embedding.create(input=[history], engine='text-embedding-ada-002')['data'][0]['embedding']

def vectorize_start_task(action):
    pass

def vectorize_process_dom(action):
    pass

def vectorize_determine_action(action):
    pass

def vectorize_perform_action(action):
    pass

def vectorize_finish_action(action):
    pass

def vectorize_finish_task(action):
    pass

def vectorize_action_error(action):
    pass

def vectorize_cancel_task(action):
    pass

vectorize_fns = {
    # 'StartTask': vectorize_start_task,
    # 'ProcessDOM': vectorize_process_dom,
    # 'DetermineAction': vectorize_determine_action,
    # 'PerformAction': vectorize_perform_action,
    # 'FinishAction': vectorize_finish_action,
    # 'FinishTask': vectorize_finish_task,
    # 'ActionError': vectorize_action_error,
    # 'CancelTask': vectorize_cancel_task,
}

def vectorize_action(action):
    if action['event_name'] in vectorize_fns:
        return vectorize_fns[action['event_name']](action)
    
    return openai.Embedding.create(input=[json.dumps(action)], engine='text-embedding-ada-002')['data'][0]['embedding']
