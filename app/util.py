from flask import request, flash, redirect, g
from database import Session, redis
from functools import wraps
from dateutil.relativedelta import relativedelta

def flashy(m, f="danger", u="/"):
    flash(m, f)
    return redirect(u)

class DummyObj(object):
    def __init__(self, kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return None

def require(**need):
    result, missing, error = {}, False, []
    for k, v in need.items():
        if k not in request.values:
            missing = True
            continue
        try:
            result[k] = v(request.values.get(k))
        except Exception as e:
            missing = True
            error.append(str(e))
    obj = DummyObj(result)
    obj._errors = error
    return obj, not missing

def authed(level=0, err=None):
    def deco(f):
        @wraps(f)
        def _f(*args, **kwargs):
            if not g.user:
                return err() if err else flashy("You must be logged in for that!")
            return f(*args, **kwargs)
        return _f
    return deco

def limit(per_minute):
    """
    Enables ratelimiting for an endpoint, is ALWAYS ignored for server
    requests.
    """
    def deco(f):
        @wraps(f)
        def _f(*args, **kwargs):
            # TODO: this could be used as a DoS attack by filling up
            #  redis. Maybe add global rate limiting?
            k = "rl:%s_%s" % (f.__name__, request.remote_addr)
            if not redis.exists(k) or not redis.ttl(k):
                redis.delete(k)
                redis.setex(k, 1, 60)
                return f(*args, **kwargs)
            if int(redis.get(k)) > per_minute:
                return "Too many requests per minute!", 429
            redis.incr(k)
            return f(*args, **kwargs)
        return _f
    return deco

def json_payload_gen(typ):
    def json_payload(obj):
        if len(obj) > 8576:
            raise Exception("Payload size too large!")
        obj = json.loads(obj)
        if not isinstance(obj, type):
            raise Exception("Invalid top-level key!")
        return obj
    return json_payload

attrs = ['years', 'months', 'days', 'hours', 'minutes', 'seconds']
human_readable = lambda delta: ['%d %s' % (getattr(delta, attr), getattr(delta, attr) > 1 and attr or attr[:-1]) for attr in attrs if getattr(delta, attr)]

MAPS = ["ns2_summit", "ns2_tram", "ns2_mineshaft", "ns2_docking", "ns2_veil",
"ns2_refinery", "ns2_biodome", "ns2_eclipse"]
