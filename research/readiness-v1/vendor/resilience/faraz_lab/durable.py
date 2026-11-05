"""Write-ahead wrapper for the pinned pure core and the exact in-memory mock.

No journal can atomically commit a broker side effect. A durable attempt precedes
the mock call; ambiguous effects/commits stop this writer until fresh recovery.
There is no checkpoint truth, retry path, terminal, socket, or broker adapter.
"""
from faraz_core import execution as core
from .journal import Journal, JournalError


class DurabilityError(RuntimeError):
    pass


class DurableExecutor:
    def __init__(self, journal, cut_hook=None):
        self.journal = journal
        self.cut_hook = cut_hook
        self.poisoned = False
        self.closed = False
        try:
            self._state = core.replay(journal.entries)
        except BaseException as error:
            journal.close()
            raise DurabilityError("INVALID_DURABLE_TRANSITION_TRACE") from error

    @classmethod
    def create(cls, path, binding, cut_hook=None, fault_hook=None):
        return cls(Journal.create(path, binding, fault_hook=fault_hook), cut_hook)

    @classmethod
    def open(cls, path, binding=None, cut_hook=None, fault_hook=None):
        executor = cls(Journal.open(path, binding, fault_hook=fault_hook), cut_hook)
        try:
            executor.transition("recover")
        except BaseException:
            executor.close()
            raise
        return executor

    @property
    def state(self):
        return self._state

    def _ready(self):
        if self.closed or self.poisoned or self.journal.poisoned:
            raise DurabilityError("RECOVERY_REQUIRED_OR_WRITER_CLOSED")

    def _cut(self, label):
        if self.cut_hook is not None:
            self.cut_hook(label)

    def _poison(self):
        self.poisoned = True
        # A conservative in-memory view, never a new durable fact or authority.
        self._state = core.recover(self._state)

    def _persist(self, candidate, reply=False):
        if candidate.trace[:len(self._state.trace)] != self._state.trace:
            raise DurabilityError("NONAPPENDING_TRANSITION")
        for entry in candidate.trace[len(self._state.trace):]:
            if reply:
                self._cut("before_reply_commit:" + entry.operation)
            else:
                self._cut("before_transition_commit:" + entry.operation)
            next_state = core.replay(self._state.trace + (entry,))
            self.journal.append(entry)
            self._state = next_state
            self._cut(("after_reply_commit:" if reply else
                       "after_transition_commit:") + entry.operation)

    def transition(self, operation, *arguments):
        self._ready()
        allowed = {function.__name__: function for function in (
            core.propose, core.approve, core.reserve, core.timeout, core.recover,
            core.update_context, core.apply_event, core.propose_stop,
            core.acknowledge_stop, core.observe_stop)}
        if operation not in allowed:
            raise ValueError("OFFLINE_TRANSITION_REQUIRED")
        if operation == "update_context" and (
                not arguments or arguments[0].account_id != self._state.binding.account_id):
            raise ValueError("JOURNAL_ACCOUNT_BINDING_IMMUTABLE")
        candidate = allowed[operation](self._state, *arguments)
        try:
            self._persist(candidate)
        except BaseException:
            self._poison()
            raise
        return self._state

    def send(self, broker, client_intent_id, fresh_authorization=None, now_ms=None):
        self._ready()
        if type(broker) is not core.MockBroker:
            raise ValueError("EXACT_OFFLINE_MOCK_REQUIRED")
        previous = self._state
        attempted = core.send_synthetic(previous, client_intent_id, fresh_authorization, now_ms)
        try:
            self._cut("before_send_attempt_commit")
            self._persist(attempted)
            self._cut("after_send_attempt_commit")
            self._cut("before_mock_call")
            # Recompute the identical pure transition in a disposable shell so
            # the original exact MockBroker can run. Its attempt is already
            # durable; no response from this shell is published before commit.
            memory = core.MemoryExecutor(trace=previous.trace)
            broker.dispatch(memory, client_intent_id, fresh_authorization, now_ms)
            self._cut("after_mock_call")
            if memory.state.trace[:len(self._state.trace)] != self._state.trace:
                raise DurabilityError("MOCK_TRANSITION_PREFIX_CONFLICT")
            self._persist(memory.state, reply=True)
        except BaseException:
            self._poison()
            raise
        return self._state

    def close(self):
        if not self.closed:
            self.closed = True
            self.journal.close()

    def __enter__(self):
        self._ready()
        return self

    def __exit__(self, *_):
        self.close()
