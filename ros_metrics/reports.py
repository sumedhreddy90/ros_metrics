import collections
import datetime
from ros_metrics.util import year_month_to_datetime, epoch_to_datetime

ONE_WEEK = datetime.timedelta(days=7)


def get_datetime_from_dict(row, time_field):
    if time_field == 'year, month':
        return year_month_to_datetime(row['year'], row['month'])
    else:
        return epoch_to_datetime(row[time_field])


def get_series(db, table, time_field, value_field, clause=''):
    series = []
    query = 'SELECT {value_field}, {time_field} from {table}'.format(**locals())
    query += ' {clause} ORDER BY {time_field}'.format(clause=clause, time_field=time_field)
    for row in db.query(query):
        series.append((get_datetime_from_dict(row, time_field), row[value_field]))
    return series


def get_aggregate_series(db, table, time_field, resolution=ONE_WEEK):
    series = []
    query = 'SELECT {time_field} FROM {table}'.format(time_field=time_field, table=table)
    query += ' WHERE {time_field} is not NULL ORDER BY {time_field}'.format(time_field=time_field)
    last_time = None
    count = 0
    for row in db.query(query):
        count += 1
        dt = get_datetime_from_dict(row, time_field)
        if last_time is None or dt - last_time > resolution:
            last_time = dt
            series.append((dt, count))
    return series


def get_unique_series(db, table, time_field, ident_field, resolution=ONE_WEEK):
    series = []
    seen = set()
    query = 'SELECT {time_field}, {ident_field} FROM {table}'.format(**locals())
    query += ' WHERE {time_field} is not NULL ORDER BY {time_field}'.format(time_field=time_field)
    last_time = None
    for row in db.query(query):
        ident = row[ident_field]
        if ident in seen:
            continue
        seen.add(ident)
        dt = get_datetime_from_dict(row, time_field)
        if last_time is None or dt - last_time > resolution:
            last_time = dt
            series.append((dt, len(seen)))
    return series


def order_by_magnitude(count_dict, remove_fields=[]):
    ordered_values = []
    for k, v in sorted(count_dict.items(), key=lambda item: item[1], reverse=True):
        if k.lower() in remove_fields:
            continue
        ordered_values.append(k)
    return ordered_values


def time_buckets(db, table, values, time_field, ident_field, value_field=None, months=True):
    buckets = collections.defaultdict(collections.Counter)
    for value in values:
        select_field = time_field
        if value_field:
            select_field += ', ' + value_field

        one_time_field = time_field.split(',')[0]
        results = db.query('SELECT {} FROM {} WHERE {} = "{}" AND {} IS NOT NULL ORDER BY {}'
                           .format(select_field, table, ident_field, value, one_time_field, time_field))
        for result in results:
            dt = get_datetime_from_dict(result, time_field)
            if months:
                key = dt.year, dt.month
            else:
                key = dt.year
            if value_field is None:
                buckets[key][value] += 1
            elif result.get(value_field):
                buckets[key][value] += result[value_field]
    return buckets


def normalize_timepoints(series_dict, values=None):
    plots = collections.defaultdict(list)
    totals = collections.defaultdict(int)

    needs_sort = False
    if values is None:
        values = set()
        for d in series_dict.values():
            values.update(d.keys())
        values = list(values)
        needs_sort = True

    for ym, line in sorted(series_dict.items()):
        total = float(sum(line.values()))
        dt = year_month_to_datetime(*ym)

        for value in values:
            v = line.get(value, 0) / total
            plots[value].append((dt, v))
            totals[value] += v

    if needs_sort:
        values = sorted(values, key=lambda value: totals[value], reverse=True)

    final_plots = collections.OrderedDict()
    for value in values:
        if totals[value] <= 0.0:
            continue
        final_plots[value] = plots[value]
    return final_plots


def get_email_plots(db):
    total = collections.Counter()
    unique = collections.Counter()
    seen = set()

    results = db.query('SELECT created_at, topic_id FROM posts WHERE created_at IS NOT NULL ORDER BY created_at')
    for result in results:
        dt = get_datetime_from_dict(result, 'created_at')
        key = dt.year, dt.month
        total[key] += 1
        ident = result['topic_id']
        if ident in seen:
            continue
        seen.add(ident)
        unique[key] += 1

    return total, unique


def buckets_to_plot(buckets):
    series = []
    for ym, value in sorted(buckets.items()):
        dt = year_month_to_datetime(*ym)
        series.append((dt, value))
    return series


def get_top_by_year(db, table, ident_field, value_field, clause='', yearly_count=15, all_time_count=15,
                    ident_tranformer=None):
    earliest = {}
    total = collections.Counter()

    for row in db.query('SELECT {}, {}, year from {} {}'.format(ident_field, value_field, table, clause)):
        ident = row[ident_field]
        if ident_tranformer:
            ident = ident_tranformer(ident)
        if not ident:
            continue
        if ident in earliest:
            earliest[ident] = min(earliest[ident], row['year'])
        else:
            earliest[ident] = row['year']
        total[ident] += row[value_field]

    yearly = collections.defaultdict(list)
    years = list(sorted(set(earliest.values())))
    for year in years[1:]:
        pkgs = [pkg for pkg in earliest if earliest[pkg] == year]
        for pkg, hits in total.most_common():
            if pkg in pkgs:
                yearly[year].append((pkg, hits))
                if len(yearly[year]) >= yearly_count:
                    break
    all_time = list(total.most_common(all_time_count))
    return all_time, yearly
