#!/bin/bash

case $1 in
    slack)
        NOTIFIER_TYPE=$1
        shift
        ;;
    *)
        echo "Please enter a valid notifier type"
        exit 1
esac

STACK_NAME="CloudCustodian${NOTIFIER_TYPE}Notifier"
CFN_TEMPLATE="${NOTIFIER_TYPE}_notifier_stack.yaml"
SCRATCH_DIR="scratch"
OUTPUT_TEMPLATE="${SCRATCH_DIR}/deploy_${CFN_TEMPLATE##*/}"
CODE_DIR="notifiers"
DEPENDS_DIR="dependencies"
PACKAGE_DIR="${SCRATCH_DIR}/${CODE_DIR}"

while [[ $# -gt 0 ]] ; do
    key=$1
    case $key in
        --stack-name)
        STACK_NAME=$2
        shift # past argument
        shift # past value
        ;;
        --bucket)
        BUCKET=$2
        shift # past argument
        shift # past value
        ;;
        --cfn-params)
        CFN_PARAMS=$2
        shift # past argument
        shift # past value
        ;;
    esac
done

if [ -z ${BUCKET} ] ; then
    echo "--bucket must be set"
    exit 1
fi

echo "Create Deploy Package"
mkdir -p ${SCRATCH_DIR}
if [ -d ${PACKAGE_DIR} ] ; then
    rm -rf ${PACKAGE_DIR}
fi

rsync -a ./${DEPENDS_DIR}/ ./${PACKAGE_DIR}/
rsync -a ./${CODE_DIR}/ ./${PACKAGE_DIR}/
#pip install --requirement package_requirements.txt --target ${PACKAGE_DIR} --quiet

aws cloudformation package --template-file ${CFN_TEMPLATE} --s3-prefix deploy --s3-bucket ${BUCKET} --output-template-file ${OUTPUT_TEMPLATE}

# Upload Package
if [ -z ${CFN_PARAMS} ] ; then
    aws cloudformation deploy --stack-name ${STACK_NAME} --template-file ${OUTPUT_TEMPLATE} --capabilities CAPABILITY_IAM
else
    aws cloudformation deploy --stack-name ${STACK_NAME} --template-file ${OUTPUT_TEMPLATE} --capabilities CAPABILITY_IAM --parameter-overrides ${CFN_PARAMS}
fi

# Display Outputs
aws cloudformation describe-stacks --stack-name ${STACK_NAME} --output text | grep OUTPUTS