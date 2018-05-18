# c7n_notifiers

c7n_notifiers is a Lambda Function enabling Cloud Custodian (c7n) to send notifications. Currently only Slack message are supported, but could be extended to support other methods of notifications, such as email, in the future.

## DESCRIPTION

Cloud Custodian supports sending notifications via SNS. This project includes a CloudFormation template that creates a SNS topic and a Lambda Function subscribed to that topic.

When a Cloud Custodian policy that includes a correctly configured `notify` action is triggered it will send a messages to the SNS topic. The Lambda Function will receive the Cloud Custodian message, extract pertinent info from that message, format that info using a specified template and then send the formatted message via the desired method.

All the code is written in Python 3.

## INSTALLATION

The CloudFormation stack can be created and updated using the `deploy.sh` script. This will create the Lambda deploy package and use the `cloudformation deploy` and `cloudformation package` commands to create/update the stack.

When using `deploy.sh` you must specify a notifier type, currently only `slack` is supported, plus the bucket to be used for the Lambda deploy package. Optionally you can specify a name for the CFN stack, otherwise one will be derived based on the notifier type.

An example of using `deploy.sh` is as follows

```
./deploy.sh slack --bucket example-bucket --stack-name example-name
```

The `deploy.sh` will output the SNS Topic Arn when it completes.

A single SNS Topic/Lambda Function (i.e. CFN Stack) can be used for multiple regions and accounts. As long as Cloud Custodian can send an SNS message to the SNS topic it can be running anywhere.

## CONFIGURATION
Configuration for the notification is done as part of the action config the Cloud Custodian policy. An example is as follows:

```
- type: notify
  to:
    - https://hooks.slack.com/services/HKGSA12/BAM6WEA11/Example
  template: reaper
  transport:
    type: sns
    topic: arn:aws:sns:us-west-2:123456789012:CloudCustodianSlackNotifier-SnsTopic-Q5ZSUVNMB77L
```

Info on each key is as follows:

| Key | Description |
|---|---|
| `type` | Must be set to `notify` |
| `to` | This is the webhook for the [Slack app](https://api.slack.com/slack-apps) that wil be used for the message |
| `template` | The template that will be used for the message. See below for more info on templates.|
| `transport` | `type` must be set to `sns` and the `topic` is the ARN for the SNS topic that will trigger the lambda. |

Jinja2 templates are used to format the notification messages that will be sent. The template to be used is specified in the Cloud Custodian policy and are located in the `templates` directory. There is a separate template for the subject and body of the notification.

The `reaper` template is specified in the policy above. This would use the `reaper.subject` and `reaper.body` templates.

Cloud Custodian must have permissions to send a message to the SNS topic.


