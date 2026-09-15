"""Seed development RBAC users and jurisdictions for LMCS."""

from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()


import asyncio
import os
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.auth import hash_password
from app.config import get_settings
from app.db import JurisdictionRow, UserRow


def required_env(name: str) -> str:
    value = os.getenv(name)

    if not value or not value.strip():
        raise RuntimeError(
            f"Missing required environment variable: {name}"
        )

    return value.strip()


DEV_JURISDICTIONS = [
    {
        "district_id": "D-PUNE",
        "district_name": "Pune",
        "state_id": "MH",
        "state_name": "Maharashtra",
        "active": True,
    },
    {
        "district_id": "D-NASHIK",
        "district_name": "Nashik",
        "state_id": "MH",
        "state_name": "Maharashtra",
        "active": True,
    },
    {
        "district_id": "D-LUDHIANA",
        "district_name": "Ludhiana",
        "state_id": "PB",
        "state_name": "Punjab",
        "active": True,
    },
    {
        "district_id": "D-JALANDHAR",
        "district_name": "Jalandhar",
        "state_id": "PB",
        "state_name": "Punjab",
        "active": True,
    },
]


USER_DEFINITIONS = [
    # ==============================================
    # NATIONAL APEX ADMINISTRATION
    # ==============================================
    {
        "id": "admin-national-01",
        "email": "ayenisha@lmcs.gov.in",
        "full_name": "Ayenisha",
        "badge_number": "LMA-NAT-001",
        "cadre": "Central Legal Metrology Administration",
        "env_var": "INITIAL_PASSWORD_AYENISHA",
        "role": "national_admin",
        "district_id": None,
        "district_name": None,
        "state_id": None,
        "state_name": None,
        "active": True,
    },
    # ==============================================
    # MAHARASHTRA / PUNE
    # ==============================================
    {
        "id": "admin-mh-pune",
        "email": "santlaj@lmcs.gov.in",
        "full_name": "Santlaj",
        "badge_number": "LMA-MH-PUNE-001",
        "cadre": "District Legal Metrology Administration",
        "env_var": "INITIAL_PASSWORD_SANTLAJ",
        "role": "district_officer",
        "district_id": "D-PUNE",
        "district_name": "Pune",
        "state_id": "MH",
        "state_name": "Maharashtra",
        "active": True,
    },
    {
        "id": "insp-mh-pune-01",
        "email": "vaishnavi@lmcs.gov.in",
        "full_name": "Vaishnavi",
        "badge_number": "LMI-MH-PUNE-001",
        "cadre": "Legal Metrology Inspectorate Cadre",
        "env_var": "INITIAL_PASSWORD_VAISHNAVI",
        "role": "inspector",
        "district_id": "D-PUNE",
        "district_name": "Pune",
        "state_id": "MH",
        "state_name": "Maharashtra",
        "active": True,
    },
    {
        "id": "insp-mh-pune-02",
        "email": "vedant@lmcs.gov.in",
        "full_name": "Vedant",
        "badge_number": "LMI-MH-PUNE-002",
        "cadre": "Legal Metrology Inspectorate Cadre",
        "env_var": "INITIAL_PASSWORD_VEDANT",
        "role": "inspector",
        "district_id": "D-PUNE",
        "district_name": "Pune",
        "state_id": "MH",
        "state_name": "Maharashtra",
        "active": True,
    },
    # ==============================================
    # PUNJAB / LUDHIANA
    # ==============================================
    {
        "id": "admin-pb-ludhiana",
        "email": "adarsh@lmcs.gov.in",
        "full_name": "Adarsh",
        "badge_number": "LMA-PB-LUDHIANA-001",
        "cadre": "District Legal Metrology Administration",
        "env_var": "INITIAL_PASSWORD_ADARSH",
        "role": "district_officer",
        "district_id": "D-LUDHIANA",
        "district_name": "Ludhiana",
        "state_id": "PB",
        "state_name": "Punjab",
        "active": True,
    },
    {
        "id": "insp-pb-ludhiana-01",
        "email": "inspector3@lmcs.gov.in",
        "full_name": "Inspector 3",
        "badge_number": "LMI-PB-LUDHIANA-001",
        "cadre": "Legal Metrology Inspectorate Cadre",
        "env_var": "INITIAL_PASSWORD_INSPECTOR3",
        "role": "inspector",
        "district_id": "D-LUDHIANA",
        "district_name": "Ludhiana",
        "state_id": "PB",
        "state_name": "Punjab",
        "active": True,
    },
    {
        "id": "insp-pb-ludhiana-02",
        "email": "inspector4@lmcs.gov.in",
        "full_name": "Inspector 4",
        "badge_number": "LMI-PB-LUDHIANA-002",
        "cadre": "Legal Metrology Inspectorate Cadre",
        "env_var": "INITIAL_PASSWORD_INSPECTOR4",
        "role": "inspector",
        "district_id": "D-LUDHIANA",
        "district_name": "Ludhiana",
        "state_id": "PB",
        "state_name": "Punjab",
        "active": True,
    },
]


async def main() -> None:
    settings = get_settings()

    engine = create_async_engine(
        settings.database_admin_url,
        pool_pre_ping=True,
    )

    Session = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with Session() as session:
            # --------------------------------------------------
            # 1. Seed Jurisdictions Independently & Idempotently
            # --------------------------------------------------
            existing_jur_res = await session.execute(
                select(JurisdictionRow.district_id)
            )
            existing_districts = set(existing_jur_res.scalars().all())

            missing_jurisdictions = [
                JurisdictionRow(
                    id=str(uuid4()),
                    district_id=item["district_id"],
                    district_name=item["district_name"],
                    state_id=item["state_id"],
                    state_name=item["state_name"],
                    active=item["active"],
                )
                for item in DEV_JURISDICTIONS
                if item["district_id"] not in existing_districts
            ]

            if missing_jurisdictions:
                session.add_all(missing_jurisdictions)
                await session.commit()
                print(f"Successfully seeded {len(missing_jurisdictions)} new jurisdictions.")
            else:
                print("All 4 development jurisdictions already exist — skip jurisdiction insert.")

            # --------------------------------------------------
            # 2. Seed Users Idempotently with Conflict Detection
            # --------------------------------------------------
            existing_users_res = await session.execute(
                select(UserRow.id, UserRow.email)
            )
            existing_records = existing_users_res.all()
            existing_by_id = {r[0]: r[1] for r in existing_records}
            existing_by_email = {r[1]: r[0] for r in existing_records}

            users_to_seed = []
            for u in USER_DEFINITIONS:
                user_id = u["id"]
                email = u["email"]

                id_exists = user_id in existing_by_id
                email_exists = email in existing_by_email

                if id_exists and email_exists:
                    if existing_by_id[user_id] != email:
                        raise RuntimeError(
                            f"Conflicting user detected: ID '{user_id}' belongs to email '{existing_by_id[user_id]}' in DB, cannot match '{email}'."
                        )
                    # Already exists, skip safely
                    continue
                elif id_exists and not email_exists:
                    raise RuntimeError(
                        f"Conflicting user detected: ID '{user_id}' already exists in DB with different email '{existing_by_id[user_id]}'."
                    )
                elif not id_exists and email_exists:
                    raise RuntimeError(
                        f"Conflicting user detected: Email '{email}' already exists in DB with different ID '{existing_by_email[email]}'."
                    )
                else:
                    users_to_seed.append(u)

            if not users_to_seed:
                print("All development RBAC users already exist — skip user insert.")
            else:
                new_user_rows = []
                for u in users_to_seed:
                    raw_password = required_env(u["env_var"])
                    new_user_rows.append(
                        UserRow(
                            id=u["id"],
                            email=u["email"],
                            full_name=u["full_name"],
                            badge_number=u["badge_number"],
                            cadre=u["cadre"],
                            password_hash=hash_password(raw_password),
                            role=u["role"],
                            district_id=u["district_id"],
                            district_name=u["district_name"],
                            state_id=u["state_id"],
                            state_name=u["state_name"],
                            active=u["active"],
                        )
                    )
                session.add_all(new_user_rows)
                await session.commit()
                print(f"Successfully seeded {len(new_user_rows)} development RBAC users.")

            print("RBAC Hierarchy Summary:")
            print("  National Admins : 1")
            print("  District Admins : 2")
            print("  Inspectors      : 4")
            print("  States          : 2")
            print("  Districts       : 4")
            print("  Jurisdictions   : 4")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())