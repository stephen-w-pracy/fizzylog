import tempfile

from fizzylog import db
from fizzylog.models import StatusFilter


def test_rollup_aggregation():
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
        db.init_db(tmp.name)
        conn = db.get_connection(tmp.name)
        try:
            db.write_rollups(
                conn,
                {
                    (100, "/", 200): 2,
                    (100, "/", 404): 1,
                    (160, "/", 200): 3,
                },
            )
            db.write_rollups(conn, {(100, "/", 200): 1})

            rows = db.query_rollups(
                conn,
                ["/"],
                StatusFilter(mode="ranges", ranges=["2xx"], exact=[]),
                100,
                160,
            )
        finally:
            conn.close()

    assert rows == [(100, "/", 3), (160, "/", 3)]
