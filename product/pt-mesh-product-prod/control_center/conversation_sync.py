"""Use the local conversation store without creating a second authority."""
import importlib.util
from pathlib import Path


def store(home):
    source=Path(home)/'.openclaw/extensions/progretech-conversation-sync/store.py'
    if not source.exists(): return None
    spec=importlib.util.spec_from_file_location('progretech_conversation_store',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.Store()


def history(home, agent):
    instance=store(home)
    if instance is None:return {'enabled':False,'events':[]}
    try:return {'enabled':True,'events':instance.history(agent,limit=100)}
    finally:instance.db.close()


def publish(home, **event):
    instance=store(home)
    if instance is None:return
    try:return instance.append(**event)
    finally:instance.db.close()


def tasks(home,office,snapshot,new_task=None):
    instance=store(home)
    if instance is None:return
    try:return instance.observe_tasks(office,snapshot,new_task)
    finally:instance.db.close()
