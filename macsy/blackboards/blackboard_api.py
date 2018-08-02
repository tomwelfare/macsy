import urllib.parse
from pymongo import MongoClient
from macsy.blackboards import blackboard, date_based_blackboard
from macsy.blackboards.managers import tag_manager, counter_manager
TagManager = tag_manager.TagManager
CounterManager = counter_manager.CounterManager
Blackboard = blackboard.Blackboard
DateBasedBlackboard = date_based_blackboard.DateBasedBlackboard

def validate_blackboard_name(func):
    ''' Validate the blackboard_name, checking if it contains forbidden characters.'''
    def wrap(*args, **kwargs):
        if any(x in args[1] for x in r" \$_"):
            raise ValueError('Forbidden characters in blackboard name ("$","_"," ")')
        return func(*args, **kwargs)
    return wrap

def validate_settings(func):
    ''' Validate the settings, checking if the right fields are present.'''
    def wrap(*args, **kwargs):
        required_fields = BlackboardAPI._setting_fields.values()
        if len(set(required_fields).intersection(args[1])) is not len(required_fields):
            raise ValueError('Incorrect or incomplete database settings supplied.')
        return func(*args, **kwargs)
    return wrap

class BlackboardAPI():
    '''Entry object for loading and deleting blackboards.'''

    _setting_fields = {'username' : 'user', 'password' : 'password', 'dbname' : 'dbname', 'dburl' : 'dburl'}
    _protected_names = ['ARTICLE', 'FEED', 'OUTLET', 'TWEET', 'URL', 'MODULE', 'MODULE_RUN', 'Newspapers', 'AmericanNews']
    _admin_user = 'dbadmin'
    _salt = ')Djmsn)p'

    @validate_settings
    def __init__(self, settings, MongoClient=MongoClient):
        '''Constructor for the BlackboardAPI.

        Args:
            settings (dict): dictionary containing the database settings to use, including
                username, password, dbname (database name) and dburl (database url).
            MongoClient (MongoClient, optional): optional MongoClient to use, generally
                useful for mocking, and testing the blackboards without connecting to a real
                database.

        Raises:
            ValueError: If incorrect or incomplete database settings are provided.
        '''
        self.__username = urllib.parse.quote_plus(settings[
            BlackboardAPI._setting_fields.get('username')])
        self.__password = urllib.parse.quote_plus(settings[
            BlackboardAPI._setting_fields.get('password')])
        self.__dbname = settings[
            BlackboardAPI._setting_fields.get('dbname')]
        self.__dburl = settings[
            BlackboardAPI._setting_fields.get('dburl')].replace('mongodb://', '').strip('/')
        self.__admin_mode = self._check_admin_attempt(settings)
        self.__client = MongoClient(self._get_connection_string(settings))
        self.__db = self.__client[self.__dbname]

    def get_blackboard_names(self):
        '''Retrieve a list of all available blackboard names.

        Returns:
            List[str]: names of available blackboards.
        '''
        suffix_len = len(CounterManager.counter_suffix)
        collections = self.__db.collection_names(include_system_collections=False)
        blackboards = (coll[0:-suffix_len] for coll in collections if coll.endswith(CounterManager.counter_suffix))
        blackboards = [blackboard for blackboard in blackboards if self.blackboard_exists(blackboard.split('_')[0])]

        return blackboards

    @validate_blackboard_name
    def blackboard_exists(self, blackboard_name):
        '''Check by name if a blackboard exists.

        Args:
            blackboard_name (str): the blackboard name to check for existence.

        Returns:
            bool: True if blackboard exists, False otherwise.

        Raises:
            ValueError: If `blackboard_name` contains forbidden characters.
        '''
        collection = self.__db[blackboard_name + CounterManager.counter_suffix]
        result = collection.find_one({CounterManager.counter_id : CounterManager.counter_type})
        if result:
            return True
        return False

    @validate_blackboard_name
    def load_blackboard(self, blackboard_name, date_based=None):
        '''Load or create (if it doesn't exist) a blackboard by name and return it.

        Args:
            blackboard_name (str): the name of the blackboard to load or create.
            date_based (bool, optional): whether or not the blackboard should be date-based or not.

        Returns:
            Blackboard object

        Raises:
            ValueError: If `blackboard_name` contains forbidden characters.
        '''
        settings = (self.__db, blackboard_name, self.__admin_mode)
        return DateBasedBlackboard(settings) \
            if self.get_blackboard_type(blackboard_name, date_based) == \
            CounterManager.counter_type_date_based else Blackboard(settings)

    @validate_blackboard_name
    def drop_blackboard(self, blackboard_name):
        '''Drop (delete) a blackboard from the database, use with caution!!


        Protected blackboards require admin permissions in order to remove them,
        to guard against the accidental deletion of the important data in the database.

        Args:
            blackboard_name (str): the name of the blackboard to delete.

        Raises:
            ValueError: If `blackboard_name` contains forbidden characters.
            PermissionError: If `blackboard_name` is a protected blackboard, and the user
                does not have admin privileges.
        '''
        protected = blackboard_name.upper() in BlackboardAPI._protected_names
        if protected and not self.__admin_mode:
            raise PermissionError(
                'Protected blackboards cannot be dropped without admin privileges.' +
                ' Attempt has been logged.')
        else:
            drop_method = {CounterManager.counter_type_standard : self.__drop_standard_blackboard,\
                CounterManager.counter_type_date_based : self.__drop_date_based_blackboard}
            blackboard_type = self.get_blackboard_type(blackboard_name)
            drop_method[blackboard_type](blackboard_name)

    @validate_blackboard_name
    def get_blackboard_type(self, blackboard_name, date_based=None):
        '''Get the type of the blackboard and return it as a string.

        Args:
            blackboard_name (str): the name of the blackboard to check.
            date_based (bool, optional): whether the blackboard is date-based or not.

        Returns:
            str: 'DATEBASED' if blackboard is date-based, 'STANDARD' otherwise.

        Raises:
            ValueError: If `blackboard_name` contains forbidden characters.
        '''
        collection = self.__db[blackboard_name + CounterManager.counter_suffix]
        result = collection.find_one({CounterManager.counter_id : CounterManager.counter_type})
        if result is not None:
            BlackboardAPI._check_blackboard_type_errors((blackboard_name, \
                result.get(CounterManager.counter_type), date_based))
            return result.get(CounterManager.counter_type)
        types = {True: CounterManager.counter_type_date_based, False: CounterManager.counter_type_standard, None: None}
        return types[date_based]

    @validate_settings
    def _get_connection_string(self, settings):
        settings = (self.__username, self.__password, \
            self.__dburl, self.__dbname, '')#'?readPreference=secondary')
        return 'mongodb://%s:%s@%s/%s%s' % settings

    @validate_settings
    def _check_admin_attempt(self, settings):
        if self.__username != BlackboardAPI._admin_user:
            self.__password += str(BlackboardAPI._salt)
            return False
        return True

    def __drop_standard_blackboard(self, blackboard_name):
        for suffix in ['', CounterManager.counter_suffix, TagManager.tag_suffix]:
            self.__db.drop_collection(blackboard_name + suffix)

    def __drop_date_based_blackboard(self, blackboard_name):
        for coll in self.__db.collection_names():
            suffix = coll.split('_')[-1]
            if blackboard_name == coll.split('_')[0] and (suffix.isdigit() or \
                suffix in CounterManager.counter_suffix or TagManager.tag_suffix):
                self.__db.drop_collection(coll)

    @staticmethod
    def _check_blackboard_type_errors(ntd):
        standard = ntd[1] == CounterManager.counter_type_standard
        atype = CounterManager.counter_type_standard if standard else \
            CounterManager.counter_type_date_based
        if ntd[2] == standard:
            raise ValueError('{} is a {} blackboard.'.format(ntd[0], atype))
