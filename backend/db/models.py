"""
SQLAlchemy ORM models for CampusRide Planner.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, ForeignKey, Index, DateTime
from sqlalchemy.orm import relationship
from backend.db.session import Base


class StandModel(Base):
    __tablename__ = "stands"

    id = Column(String(16), primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    zone = Column(String(32), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    dock_capacity = Column(Integer, nullable=False)
    origin_weight = Column(Float, default=0.1, nullable=False)
    destination_weight = Column(Float, default=0.1, nullable=False)

    trips_origin = relationship("TripRecordModel", foreign_keys="TripRecordModel.origin_stand_id", backref="origin_stand")
    trips_dest = relationship("TripRecordModel", foreign_keys="TripRecordModel.dest_stand_id", backref="dest_stand")


class TripRecordModel(Base):
    __tablename__ = "trip_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    request_time_sec = Column(Float, nullable=False)      # Seconds from 00:00
    origin_stand_id = Column(String(16), ForeignKey("stands.id"), nullable=False)
    dest_stand_id = Column(String(16), ForeignKey("stands.id"), nullable=False)
    user_type = Column(String(16), default="student", nullable=False)
    max_wait_minutes = Column(Float, default=5.0, nullable=False)
    is_synthetic = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_trip_date_origin", "date", "origin_stand_id"),
        Index("idx_trip_date_dest", "date", "dest_stand_id"),
    )


class HourlyDemandModel(Base):
    __tablename__ = "hourly_demand"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    hour = Column(Integer, nullable=False)                  # 0 to 23
    stand_id = Column(String(16), ForeignKey("stands.id"), nullable=False)
    pickups_actual = Column(Integer, default=0, nullable=False)
    dropoffs_actual = Column(Integer, default=0, nullable=False)
    temp_celsius = Column(Float, nullable=True)
    precipitation_mm = Column(Float, nullable=True)

    __table_args__ = (
        Index("idx_demand_date_hour_stand", "date", "hour", "stand_id", unique=True),
    )


class SurveyResponseModel(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    anonymized_id = Column(String(32), unique=True, nullable=False)
    home_stand_id = Column(String(16), ForeignKey("stands.id"), nullable=False)
    primary_dest_stand_id = Column(String(16), ForeignKey("stands.id"), nullable=False)
    morning_commute_hour = Column(Integer, nullable=False)
    evening_commute_hour = Column(Integer, nullable=False)
    cycle_in_rain = Column(Boolean, default=False, nullable=False)
    acceptable_walk_minutes = Column(Float, default=5.0, nullable=False)
