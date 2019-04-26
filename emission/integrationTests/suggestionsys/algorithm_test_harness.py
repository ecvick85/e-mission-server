import sys
import logging
# Change this to INFO if you want less verbose logging
logging.basicConfig(level=logging.DEBUG)
import argparse
import json

import emission.core.wrapper.suggestion_sys as sugg

def test_find_destination_business(cfn, params, exp_output):
    lat, lon = sugg.geojson_to_lat_lon_separated(params["loc"])
    result = cfn(lat, lon)
    name = result[0]
    # exp_output is a list of valid names
    if name in exp_output:
        logging.debug("found match! name = %s, comparing with %s" %
            (name, exp_output))
        return True
    else:
        logging.debug("no match! name = %s, comparing with %s" %
            (name, exp_output))
        return False

def test_category_of_business_nominatim(cfn, params, exp_output):
    lat, lon = sugg.geojson_to_lat_lon_separated(params["loc"])
    result = cfn(lat, lon)
    return exp_output == result

def test_calculate_yelp_server_suggestion_for_locations(cfn, params, exp_output):
    start_loc = params["start_loc"]
    end_loc = params["end_loc"]
    distance_in_miles = sugg.distance(sugg.geojson_to_latlon(start_loc), sugg.geojson_to_latlon(end_loc))
    distance_in_meters = distance_in_miles / 0.000621371
    logging.debug("distance in meters = %s" % distance_in_meters)
    # calculation function expects distance in meters
    result = cfn(start_loc, end_loc, distance_in_meters)
    return result.get('businessid', None) == exp_output

def test_single_instance(test_fn, cfn, instance):
    logging.debug("-----" + instance["test_name"] + "------")
    param = instance["input"]
    exp_output = instance["output"]
    result = test_fn(cfn, param, exp_output)
    if not result:
        logging.debug("Test %s failed, output = %s, expected %s "
            % (instance["test_name"], result, exp_output))
    return result

# Note: this has to be here because it needs to be after the
# wrapper function is defined but before we use the keys as valid choices while
# setting up the parser

TEST_WRAPPER_MAP = {
    "find_destination_business": test_find_destination_business,
    "category_of_business_nominatim": test_category_of_business_nominatim,
    "calculate_yelp_server_suggestion_for_locations": test_calculate_yelp_server_suggestion_for_locations
}

CANDIDATE_ALGORITHMS = {
    "find_destination_business": [
        sugg.find_destination_business_google,
        sugg.find_destination_business_yelp,
        sugg.find_destination_business_nominatim,
        sugg.find_destination_business
    ],
    "category_of_business_nominatim": [
        sugg.category_of_business_nominatim,
        sugg.category_from_name_wrapper,
        sugg.category_from_address_wrapper,
        sugg.category_of_business_awesome
    ],
    "calculate_yelp_server_suggestion_for_locations": [
        sugg.calculate_yelp_server_suggestion_for_locations
    ]
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
#     parser.add_argument("-d", "--debug", type=int,
#         help="set log level to DEBUG")
    parser.add_argument("algorithm",
        choices=TEST_WRAPPER_MAP.keys(),
        help="the algorithm to test")
    parser.add_argument("--candidates", nargs="*",
        help="the candidate implementations of the algorithm; see suggestion_sys for details")
    parser.add_argument("-f", "--infile",
        help="the file that has the inputs and expected outputs. default is emission/integrationTests/suggestionsys/{algorithm}.dataset.json")
    parser.add_argument("-t", "--test", nargs="+",
        help="run only the test with the specific name, to make it easier to debug individual instances")

    args = parser.parse_args()
#     if args.debug:
#         logging.basicConfig(level=logging.DEBUG)
#     else:
#         logging.basicConfig(level=logging.INFO)

    if args.infile is None:
        args.infile = ("emission/integrationTests/suggestionsys/%s.dataset.json"
            % (args.algorithm))

    test_fn = TEST_WRAPPER_MAP[args.algorithm]
    logging.info("Mapped algorithm %s -> %s" % (args.algorithm, test_fn))

    all_candidate_fn_list = CANDIDATE_ALGORITHMS[args.algorithm]
    all_candidate_name_list = [c.__name__ for c in CANDIDATE_ALGORITHMS[args.algorithm]]
    if args.candidates is None:
        args.candidates = all_candidate_name_list

    logging.info("specified candidates = %s" % args.candidates)
    invalid_candidate_fn_names = [c for c in args.candidates
        if c not in all_candidate_name_list]
    if len(invalid_candidate_fn_names) > 0:
        print("Did not find candidate algorithms %s" % invalid_candidate_fn_names)
        exit(1)

    candidate_fns = [fn for fn in all_candidate_fn_list if fn.__name__ in args.candidates]
    logging.info("Comparing candidate functions %s" % candidate_fns)

    dataset = json.load(open(args.infile))

    if args.test is not None:
        logging.info("Running single test %s" % args.test)
        test_instance = [i for i in dataset if i["test_name"] == " ".join(args.test)][0]
        logging.debug("Found test instance %s" % test_instance)
        for cfn in candidate_fns:
            test_single_instance(test_fn, cfn, test_instance)
        exit(0)

    cfn2resultlist= []
    for cfn in candidate_fns:
        successfulTests = 0
        failedTests = 0
        for instance in dataset:
            result = test_single_instance(test_fn, cfn, instance)
            if result:
                successfulTests = successfulTests + 1
            else:
                failedTests = failedTests + 1
            logging.debug("For candidate %s, after instance %s, successfulTests = %d, failedTests = %d"
                % (cfn.__name__, instance["test_name"], successfulTests, failedTests))
        cfn2resultlist.append((cfn.__name__, successfulTests, failedTests))
        logging.info("Testing candidate %s complete, overall accuracy = %s " %
            (cfn.__name__, (successfulTests * 100) / (successfulTests + failedTests)))

    logging.info("Test complete, comparison results = ")
    for cfn_name, successfulTests, failedTests in cfn2resultlist:
        logging.info("candidate: %s, accuracy = %s" % (cfn_name, (successfulTests * 100) / (successfulTests + failedTests)))

