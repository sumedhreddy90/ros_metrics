from ros_metrics.analytics import update_analytics
from ros_metrics.answers import update_answers
from ros_metrics.discourse import update_discourse
from ros_metrics.packages import update_packages
from ros_metrics.rosdistro import update_rosdistro
from ros_metrics.ros_users import update_ros_users
from ros_metrics.scholar import update_scholar
import argparse

if __name__ == '__main__':
    modules = {
        'analytics': update_analytics,
        'answers': update_answers,
        'discourse': update_discourse,
        'packages': update_packages,
        'rosdistro': update_rosdistro,
        'ros_users': update_ros_users,
        'scholar': update_scholar,
    }

    parser = argparse.ArgumentParser()
    parser.add_argument('modules', metavar='module', choices=sorted(list(modules.keys()) + ['all']), nargs='*',
                        default='all')
    args = parser.parse_args()
    if 'all' in args.modules:
        args.modules = list(modules.keys())

    for key in args.modules:
        modules[key]()
