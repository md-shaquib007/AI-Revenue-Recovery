from datetime import datetime, timedelta, timezone
from typing import List, Optional


class SalaryWindowPredictor:
    """
    Intelligent Salary Cycle & Liquidity Predictor.
    Analyzes historical payment success patterns to schedule zero-bounce
    collection sweeps aligned with Indian payroll influx windows.
    """

    WINDOWS = {
        "CORPORATE_PAYROLL": [28, 29, 30, 31, 1, 2],    # 1st of month (84% corporate salaried)
        "MID_MARKET_PAYROLL": [5, 6, 7],                # 5th of month (SME / Startups)
        "FORTNIGHTLY_PAYROLL": [10, 11, 12, 15],         # 10th/15th of month (Gig / Bi-weekly)
    }

    @classmethod
    def predict_salary_day(cls, past_success_dates: Optional[List[datetime]] = None) -> int:
        """
        Determines the customer's most probable salary inflow date.
        Defaults to the 1st of the month if insufficient history.
        """
        if not past_success_dates:
            return 1

        days = [d.day for d in past_success_dates if isinstance(d, datetime)]
        if not days:
            return 1

        # Count cluster frequencies
        corporate_count = sum(1 for d in days if d in cls.WINDOWS["CORPORATE_PAYROLL"])
        mid_market_count = sum(1 for d in days if d in cls.WINDOWS["MID_MARKET_PAYROLL"])
        fortnightly_count = sum(1 for d in days if d in cls.WINDOWS["FORTNIGHTLY_PAYROLL"])

        if corporate_count >= mid_market_count and corporate_count >= fortnightly_count:
            return 1
        elif mid_market_count > corporate_count and mid_market_count >= fortnightly_count:
            return 5
        elif fortnightly_count > 0:
            return 10

        return 1

    @classmethod
    def calculate_next_sweep_time(cls, predicted_salary_day: int, reference_time: Optional[datetime] = None) -> datetime:
        """
        Computes the next optimal execution timestamp: 06:30 AM IST (01:00 AM UTC)
        on the customer's predicted payroll credit date.
        """
        ref = reference_time or datetime.now(timezone.utc)
        year = ref.year
        month = ref.month

        # Target 01:00 UTC (06:30 IST)
        try:
            target_date = datetime(year, month, predicted_salary_day, 1, 0, 0, tzinfo=timezone.utc)
        except ValueError:
            target_date = datetime(year, month, 28, 1, 0, 0, tzinfo=timezone.utc)

        # If the target date in current month has already passed, schedule for next month
        if target_date <= ref:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            try:
                target_date = datetime(year, month, predicted_salary_day, 1, 0, 0, tzinfo=timezone.utc)
            except ValueError:
                target_date = datetime(year, month, 28, 1, 0, 0, tzinfo=timezone.utc)

        return target_date


salary_predictor = SalaryWindowPredictor()
