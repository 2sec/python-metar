import os
import random


import Log


# random init for all modules
random_state = 1217
os.environ['PYTHONHASHSEED'] = '0'
random.seed(random_state)
#np.random.seed(random_state)



GAE_PROJECTID = os.getenv('GOOGLE_CLOUD_PROJECT', '')
GAE_BUCKET = GAE_PROJECTID + '.appspot.com'
GAE_ENV = os.getenv('GAE_ENV', '')

USE_GAE = GAE_PROJECTID != ''
BUCKET = GAE_BUCKET

USE_AWS = False

AWS_PROJECTID = os.getenv('AWS_PROJECT', '')
AWS_BUCKET = os.getenv('AWS_BUCKET', '')
AWS_ENV = os.getenv('AWS_ENV', '')

if AWS_PROJECTID != '':
    USE_AWS = True
    USE_GAE = False
    BUCKET = AWS_BUCKET


Log.Write('GOOGLE_CLOUD_PROJECT = ' + GAE_PROJECTID)
Log.Write('GAE_ENV = ' + GAE_ENV)
Log.Write('AWS_PROJECT = ' + AWS_PROJECTID)
Log.Write('AWS_BUCKET = ' + AWS_BUCKET)
Log.Write('AWS_ENV = ' + AWS_ENV)



is_production = GAE_ENV != '' or AWS_ENV != ''
local_download = not is_production