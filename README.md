**_Be warned_: this is very experimental!**


Contributing
------------

The code needs some cleanup, and might not be obvious at all.  All of this is
very much the result of myself hacking around in it for way too long.  Please
do add GitHub comments for lines that are unclear, and I'll explain they're in
there.  This bit of communication will be vital in developing a common
understanding of the new model.

Any help with this is really appreciated!

To run the workers (all executing fake work for now):

    $ python main.py forking 4  # will start 4 pre-forked child processes
    $ python main.py gevent 10  # will use 10 greenlets


The New and Shiny RQ Concurrent Workers
---------------------------------------

This is a temporary project that I use to flesh out the bodies of the main new
worker structure for concurrent RQ workers.  The main reason for putting this
in a separate repository is to fight complexity without the burden of the
existing RQ code base.  The new concurrent worker structure is complex enough
on its own, without any RQ details.

This project contains no notion of "Redis", "jobs", "queues", or whatever RQ's
jargon.  What it _does_ concern are "workers" and "work horses", or as they're
called in the new structure "children".

The new worker structure differs a lot from the current, non-concurrent, worker
structure, which I'll explain below.


The Status Quo
--------------

This is how RQ versions before 0.4 work.

The work loop:

- At the top, there's the worker process (a single Unix process)
- This worker connects to Redis and listens for incoming work on queues using
  the blocking `BLPOP` call
- If such a job is received, it forks and lets its forked child (called the
  "work horse") execute the work
- It waits until the work horse is done
- It loops

Hence, at most 2 Unix processes will exist at the same time.  There is no
concurrency control in RQ workers whatsoever.  Processing more jobs
concurrently is possible only by starting more workers.

The termination logic is as follow:

- Either `SIGINT` ("Ctrl+C") or `SIGTERM` terminates the loop gracefully.  The
  main worker catches these and activates abortion: it sets a flag to stop the
  loop after the current work horse is done
- The work horse ignores any signal and always continues its work
- If a second `SIGINT` or `SIGTERM` is fired during this waiting period, cold
  shutdown kicks in, meaning the main worker will forcefully kill the work horse
- A cold shutdown means work is brutefully terminated and work is lost


New worker structure
--------------------

**New terminology**: In the new situation, the term "work horse" will be
avoided.  Instead, we'll refer to the unit of concurrency that performs the
actual work as the "worker child", or simply "child", whether that'd be
a process, a thread, or a greenlet.

Changes from 10,000 ft.:

- RQ workers are concurrent, meaning a single worker _can_ run multiple jobs at
  the same time, without help from another worker.
- Multiple concurrency mechanics can be used, like the good old forking,
  multiprocessing, threading and gevent-style cooperative multitasking (pick
  whatever suits you best)
- The forking worker will still be the default, and still be 1 child by default
  (same as pre-0.4).  Concurrency should be enabled explicitly.
- Abortion semantics and behaviour should not change from a user's perspective:

    * A single `SIGINT` or `SIGTERM` should activate warm shutdown (i.e. wait
  	  indefinitely for all current work to finish, but then stop)
    * While that waiting period is active, a second `SIGINT` or `SIGTERM` will
  	  have the main worker brutally kill every child, losing work
    * This behaviour is predictable and exactly the same for all concurrency
  	  mechanisms, no matter if forking, multiprocessing, threading, or gevent is
  	  used.


Under the hood
--------------

Most of the complexity is introduced by the very last requirement.  I've often
stopped and asked myself whether this is the way to go, as each concurrency
mechanism has roughly different semantics that might not fit this use case very
well.  Nevertheless, I could not find piece of mind with workers behaving very
differently depending on the concurrency backend that was used---it had weird
behavioural differences.  This is the main reason why [the GitHub issue for
concurrency][1] has been open for over 10 months now.

Let's take a look at the main worker loop.  Compared to the pre-0.4 state of
affairs, the main worker loop has become simpler from a high-level perspective,
as most of the job's details will now be delegated to the children.

The main worker loops indefinitely, spawning children (of the currently used
backend: so either processes, threads or greenlets) from a "pool-like" object
that either (1) returns a new spawned child, or (2) blocks until there's room
for such a child in the pool.  Since this is, by definition, an eventually
blocking call, this can be called in an endless loop.

This behaviour is exactly modeled after `gevent.pool.Pool`'s behaviour, which
is super handy.  Starting a worker now means children are spawned upfront and
are able to immediately execute work.  The number of spawned children is
maximal right after the main worker is started, all waiting for work
individually.  In other words: it is _not the case_ that children are spawned
as there is work for them.

Each spawned child then does the following.  They connect to Redis and each
perform a `BLPOP` call.  When they receive work, they execute it (nothing
differs from the pre-0.4 situation from here forward).

This, too, is a simplification, but one thing becomes more complex: handling
worker termination with warm and cold shutdowns. Here's why.

Basically, the problem is to know for sure when a worker is safe to terminate.
Before 0.4, the main worker `BLPOP`'ed work from the queue first, then spawned
a work horse.  It's easy then: the work horse should never be terminated: it is
always doing important stuff.

In the new situation, though, the child has two "stages": (1) it waits (blocks)
in `BLPOP` until work is retrieved from Redis, and (2) it executes work.  It's
clear that children in stage (1) _should_ be terminated when warm shutdown is
requested, while children in stage (2) _must not_ be terminated.  Making this
distinction means children need to communicate to the main worker about their
idle state.  (By the way, note that this is different from the job
states---don't confuse them.)

To enable this nuance, we need a few extra data structures to create an "idle
state" administration.  The exact data structures to use depend heavily on the
concurrency implementation used.

[1]: https://github.com/nvie/rq/issues/45
