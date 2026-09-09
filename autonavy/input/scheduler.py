"""Bounded newest-value pending work; release deadlines live with actual holds."""
class Pending:
    def __init__(self, limit):
        self.limit = limit
        self.items = {}

    def put(self, intent):
        key = intent.owner, intent.action, intent.resource
        if key not in self.items and len(self.items) >= self.limit:
            return False
        self.items[key] = intent
        return True

    def take(self):
        values = sorted(self.items.values(), key=lambda i: -i.priority)
        self.items.clear()
        return values

    def cancel(self, owner=None):
        self.items = {k:v for k,v in self.items.items() if owner is not None and v.owner != owner}
