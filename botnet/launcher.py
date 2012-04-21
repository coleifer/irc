#!/usr/bin/env python

import logging
import optparse
import time
import sys

import boto

logger = logging.getLogger('botnet.bootstrap')


class BotNetLauncher(object):
    def __init__(self, worker_options, aws_key=None, aws_secret=None, image_id='ami-ab36fbc2',
                 instance_type='t1.micro', key_name=None, security_group=None, workers=None, quiet=False,
                 bootstrap_script='bootstrap.sh'):
        
        self.worker_options = worker_options
        self.aws_key = aws_key
        self.aws_secret = aws_secret
        self.image_id = image_id
        self.instance_type = instance_type
        self.key_name = key_name
        self.security_group = security_group
        self.workers = workers
        self.quiet = quiet
        self.bootstrap_script = bootstrap_script

        if self.security_group:
            self.security_group = [self.security_group]
    
    def get_conn(self):
        return boto.connect_ec2(self.aws_key, self.aws_secret)
    
    def get_instances(self):
        ec2 = self.get_conn()
        filters = {'tag:irc': '1'}
        return ec2.get_all_instances(filters=filters)
    
    def get_user_data(self):
        fh = open(self.bootstrap_script)
        contents = fh.read()
        fh.close()
        return contents % {
            'worker_options': self.worker_options,
        }
    
    def wait_instances(self, instances):
        i_states = dict((i, False) for i in instances)
        
        running = lambda i: i.state == 'running'
        
        while not all(i_states.values()):
            for instance, is_running in i_states.items():
                if is_running:
                    continue
                
                instance.update()
                if not self.quiet:
                    sys.stdout.write('.')
                    sys.stdout.flush()
                
                if instance.state == 'running':
                    i_states[instance] = True
            
            time.sleep(3)
    
    def launch(self):
        if not self.quiet:
            print 'About to create %d instances' % self.workers
            if raw_input('Continue Yn ?') == 'n':
                sys.exit(0)

        ec2 = self.get_conn()
        
        logger.info('Reading script %s' % self.bootstrap_script)
        user_data = self.get_user_data()

        logger.info('AMI [%s] - starting %d instances' % (self.image_id, self.workers))
        reservation = ec2.run_instances(
            self.image_id,
            min_count=self.workers,
            key_name=self.key_name,
            security_groups=self.security_group,
            instance_type=self.instance_type,
            user_data=user_data
        )

        instances = reservation.instances
        
        logger.info('Waiting for instances')
        self.wait_instances(instances)

        for instance in instances:
            instance.add_tag('irc', '1')
        
        if not self.quiet:
            print '\nSummary\n'
            for instance in instances:
                print '\nInstance ID: %s\n  AMI=%s\n  DNS=%s' % (instance.id, instance.image_id, instance.dns_name)

        return instances
    
    def terminate(self):
        reservations = self.get_instances()
        instance_ids = [i.id for r in reservations for i in r.instances]
        print 'About to terminate the following %d instances:\n%s' % (len(instance_ids), ', '.join(instance_ids))
        if raw_input('Really stop? yN ') == 'y':
            ec2 = self.get_conn()
            print ec2.terminate_instances(instance_ids)
    
    def show(self):
        reservations = self.get_instances()
        
        if reservations:
            for res in reservations:
                print 'Reservation %s' % res.id
                for instance in res.instances:
                    print '\nInstance ID: %s\n  AMI=%s\n  DNS=%s' % (instance.id, instance.image_id, instance.dns_name)
                print '\n'
        else:
            print 'No reservations found'

    def help(self):
        parser = get_parser()
        parser.print_help()

        print '\nAvailable commands:'
        for cmd in self.get_command_mapping():
            print '  - %s' % cmd
    
    def get_command_mapping(self):
        return {
            'launch': self.launch,
            'terminate': self.terminate,
            'show': self.show,
            'help': self.help,
        }
    
    def handle(self, cmd):
        commands = self.get_command_mapping()
        return commands[cmd]()


def get_parser():
    parser = optparse.OptionParser(usage='%prog [cmd] [options]')
    parser.add_option('--workers', dest='workers', type='int', default=1,
        help='Number of instances/workers to start')
    parser.add_option('--quiet', '-q', dest='quiet', action='store_true')
    parser.add_option('--script', dest='bootstrap_script', default='bootstrap.sh')
    
    boto_ops = parser.add_option_group('EC2 options')
    boto_ops.add_option('--ami', dest='image_id', default='ami-ab36fbc2')
    boto_ops.add_option('--key', dest='aws_key')
    boto_ops.add_option('--secret', dest='aws_secret')
    boto_ops.add_option('--type', dest='instance_type', default='t1.micro')
    boto_ops.add_option('--key-name', dest='key_name', help='Security key name (e.g. master-key)')
    boto_ops.add_option('--group', dest='security_group', help='Security group (e.g. default)')
    
    # --- for workers ---
    worker_ops = parser.add_option_group('Worker options')
    worker_ops.add_option('--server', '-s', dest='server',
        help='IRC server to connect to')
    worker_ops.add_option('--port', '-p', dest='port',
        help='Port to connect on', type='int')
    worker_ops.add_option('--nick', '-n', dest='nick',
        help='Nick to use')
    worker_ops.add_option('--boss', '-b', dest='boss')
    worker_ops.add_option('--logfile', '-f', dest='logfile')
    worker_ops.add_option('--verbosity', '-v', dest='verbosity')
    
    return parser

if __name__ == '__main__':    
    parser = get_parser()
    (options, args) = parser.parse_args()
    
    worker_options = {
        'server': 's', 
        'port': 'p',
        'nick': 'n',
        'boss': 'b',
        'logfile': 'f',
        'verbosity': 'v',
    }
    ops_list = []
    for k, v in worker_options.items():
        worker_op = getattr(options, k)
        if worker_op:
            ops_list.append('-%s %s' % (v, worker_op))
    worker_options = ' '.join(ops_list)
    
    launcher_options = ['aws_key', 'aws_secret', 'instance_type', 'key_name', 'security_group', 'image_id', 'workers', 'quiet']
    launcher_config = dict((k, getattr(options, k)) for k in launcher_options)
    
    launcher = BotNetLauncher(worker_options, **launcher_config)
    
    if not options.quiet:
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.ERROR)
    
    if args:
        if len(args) != 1:
            print 'Error, incorrect number of arguments specified'
            parser.print_help()
            sys.exit(1)
        cmd = args[0]
        try:
            launcher.handle(cmd)
        except KeyError:
            print 'Unknown command %s' % cmd
            print 'Valid commands: %s' % (', '.join(launcher.get_command_mapping().keys()))
            parser.print_help()
            sys.exit(2)
    else:
        launcher.launch()
