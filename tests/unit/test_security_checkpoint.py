from unittest.mock import MagicMock
from app.agent import security_checkpoint
from google.adk.events.event import Event

def test_security_checkpoint_valid_gpa():
    ctx = MagicMock()
    ctx.session.id = "test-session"
    
    # 8.7 cgpa should be valid and continue
    event = security_checkpoint._func(ctx, "Student has 8.7 cgpa and loves AI.")
    assert event.actions.route == "continue"
    assert "8.7" in event.output

def test_security_checkpoint_invalid_gpa():
    ctx = MagicMock()
    ctx.session.id = "test-session"
    
    # 14.5 GPA should be blocked
    event = security_checkpoint._func(ctx, "I have a GPA of 14.5 and study CS.")
    assert event.actions.route == "security_violation"
    assert "security_error" in event.actions.state_delta
    assert event.actions.state_delta["security_error"] == "Invalid GPA. GPA must be between 0.0 and 10.0."

def test_security_checkpoint_pii_redaction():
    ctx = MagicMock()
    ctx.session.id = "test-session"
    
    # Email and phone should be redacted
    event = security_checkpoint._func(ctx, "My email is test@domain.com and phone is 123-456-7890.")
    assert event.actions.route == "continue"
    assert "[EMAIL_REDACTED]" in event.output
    assert "[PHONE_REDACTED]" in event.output
