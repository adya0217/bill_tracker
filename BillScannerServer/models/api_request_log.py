

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, Index
from sqlalchemy.sql import func

from database import Base


class ApiRequestLog(Base):
 

    __tablename__ = "api_request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    method = Column(String(16), nullable=False)
    path = Column(String(2048), nullable=False)
    query_string = Column(Text, nullable=True)

    client_ip = Column(String(128), nullable=True)
    user_agent = Column(Text, nullable=True)

    status_code = Column(Integer, nullable=False, index=True)
    duration_ms = Column(Float, nullable=False)

    is_failure = Column(Boolean, nullable=False, default=False, index=True)

    # Truncated JSON/text response body when status_code >= 400 (for debugging client/API errors).
    failure_response_body = Column(Text, nullable=True)

    # Filled only when an unhandled exception occurred (stack trace, truncated).
    server_traceback = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_api_request_logs_path_created", "path", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ApiRequestLog id={self.id} {self.method} {self.path} "
            f"status={self.status_code} failure={self.is_failure}>"
        )
