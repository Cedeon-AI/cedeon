"""Data access. Every query is scoped to a tenant where the entity has one.

Repositories accept an ``AsyncSession`` and return ORM instances. They do not
commit — that is the service layer's job.
"""
