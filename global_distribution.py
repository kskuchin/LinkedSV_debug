#!/usr/bin/env python 
import os
import sys
from bed import *
from my_utils import *
import numpy as np
from fragment import *
import math

tab  = '\t'
endl = '\n'
arg = sys.argv[1:]

def main():

    args, dbo_args, endpoint_args = parse_user_arguments()
    estimate_global_distribution(args, dbo_args, endpoint_args)
    return

def estimate_global_distribution(args, dbo_args, endpoint_args):

    myprint('calculating distribution parameters')
    global_dist_fp = open(args.global_distribution_file, 'w')

    args.num_reads_genome = line_count(args.bcd_file)
    global_dist_fp.write('num_reads_genome\t%d\n' % args.num_reads_genome)
    myprint ('total number of reads: %d' % args.num_reads_genome) 

    if args.is_wgs == False:
        ### get reads in target region ###
        target_region_bed_file = args.target_region_bed
        target_region_tidbed_file = target_region_bed_file + '.tidbed'

        bed2tidbed_file(target_region_bed_file, args.chrname2tid, target_region_tidbed_file)

        cmd = args.bedtools + ' intersect -wa -u -a ' + args.bcd_file + ' -b ' + target_region_tidbed_file +  ' > ' + args.bcd_file_of_target_region
        os.system(cmd)
        if os.path.getsize(args.bcd_file_of_target_region) <= 0:
            myprint('failed to get reads in target region')
            sys.exit()

        args.num_reads_ontarget  = line_count(args.bcd_file_of_target_region)
        args.num_reads_offtarget = args.num_reads_genome - args.num_reads_ontarget
        global_dist_fp.write('num_reads_ontarget\t%d\n' % args.num_reads_ontarget)
        global_dist_fp.write('num_reads_offtarget\t%d\n' % args.num_reads_offtarget)

        myprint ('number of reads in target region: %d' % args.num_reads_genome)
        myprint ('number of reads in off-target region: %d' % args.num_reads_ontarget) 

    get_fragment_parameter(args, dbo_args, endpoint_args, global_dist_fp)

    global_dist_fp.close()
    cut_quantile = 0.99
    if args.is_wgs:
        args.gap_distance_cutoff = math.log(1.0 - cut_quantile) / math.log(1.0 - args.read_per_bp_genome)
    else:
        args.gap_distance_cutoff = 20 * 1000
   
    args.global_distribution_calculated = True
    return

def fit_geometric_distribution(length_list, readpair=True):

    cdf1     = [90.0, 92.0, 94.0, 96.0, 98.0]
    if readpair == True:
        cdf2 = [95.0, 96.0, 97.0, 98.0, 99.0]
    else:
        cdf2 = cdf1
    k = np.percentile(length_list, cdf2)
    p_list = list()
    for i in range(0, len(cdf1)):
        p = 1.0 - math.pow( (1.0 - cdf1[i]/100.0), (1.0 / (k[i]+1.0)) )
        p_list.append(p)

    pmedian = np.median(p_list)
    return pmedian
    
def get_fragment_parameter(args, dbo_args, endpoint_args, global_dist_fp):

    frm_length_list = list()
    bcd22_fp = open(endpoint_args.tmpbcd22_file, 'r')
    while 1:
        line = bcd22_fp.readline()
        if not line: break
        if line[0] == '#': continue
        line = line.strip().split(tab)
        frm = Fragment(line)
        frm_length_list.append(frm.length)

    N5_length, N25_length, N50_length, N75_length, N95_length, total_length = calculate_length_statistics(frm_length_list)
    myprint('N5, N25, N50, N75, N95 fragment lengths are %d, %d, %d, %d, %d' % (N5_length, N25_length, N50_length, N75_length, N95_length))
    endpoint_args.min_frag_length = max(N95_length, endpoint_args.min_frag_length)
    global_dist_fp.write('endpoint_args.min_frag_length\t%d\n' % endpoint_args.min_frag_length)

    args.fragment_length_lmda = fit_geometric_distribution(frm_length_list, readpair = False) 
    global_dist_fp.write('fragment_length_lmda\t%.20f\n' % args.fragment_length_lmda)

    bcd22_fp.seek(0, 0)

    bcd_count_dict = dict()
    total_num_reads_in_fragment = 0
    total_num_fragment = 0
    total_gap_distance_list = list()
    frm_length_list = list()
    while 1:
        line = bcd22_fp.readline()
        if not line: break
        if line[0] == '#': continue
        line = line.strip().split(tab)
        frm = Fragment(line)
        if frm.length < endpoint_args.min_frag_length: continue
        frm_length_list.append(frm.length)
        if frm.bcd not in bcd_count_dict: 
            bcd_count_dict[frm.bcd] = 1
        else:
            bcd_count_dict[frm.bcd] += 1

        total_num_reads_in_fragment += frm.num_reads
        total_num_fragment += 1
        total_gap_distance_list += frm.gap_distances() 

    bcd22_fp.close()

    args.median_fragment_length = np.median(frm_length_list)
    args.mean_fragment_length = np.mean(frm_length_list) 
    myprint('median and mean fragment lengths are %d, %d' % (args.median_fragment_length, args.mean_fragment_length))
    global_dist_fp.write('median_fragment_length\t%d\n' % args.median_fragment_length)
    global_dist_fp.write('mean_fragment_length\t%d\n' % args.mean_fragment_length)

    args.gap_distance_lmda = fit_geometric_distribution(total_gap_distance_list, readpair=True) 
    global_dist_fp.write('gap_distance_lmda\t%.20f\n' % args.gap_distance_lmda)
   
    q = [50, 75, 90, 95, 99, 99.9]
    quantile_nparray = np.percentile(total_gap_distance_list, q)
    args.gap_distance500 = quantile_nparray[0] 
    args.gap_distance750 = quantile_nparray[1] 
    args.gap_distance900 = quantile_nparray[2] 
    args.gap_distance950 = quantile_nparray[3] 
    args.gap_distance990 = quantile_nparray[4] 
    args.gap_distance999 = quantile_nparray[5]

    global_dist_fp.write('gap_distance500\t%d\n' % args.gap_distance500)
    global_dist_fp.write('gap_distance750\t%d\n' % args.gap_distance750)
    global_dist_fp.write('gap_distance900\t%d\n' % args.gap_distance900)
    global_dist_fp.write('gap_distance950\t%d\n' % args.gap_distance950)
    global_dist_fp.write('gap_distance990\t%d\n' % args.gap_distance990)
    global_dist_fp.write('gap_distance999\t%d\n' % args.gap_distance999)

    num_barcode = len(bcd_count_dict) 
    if num_barcode < 1:
        myprint ('ERROR! no effective barcode is found')
        sys.exit()

    num_fragment_per_bcd_list = list() 
    for bcd in bcd_count_dict:
        num_fragment_per_bcd_list.append(bcd_count_dict[bcd])
    
    args.mean_num_fragment_per_bcd = np.mean(num_fragment_per_bcd_list)
    args.median_num_fragment_per_bcd = np.median(num_fragment_per_bcd_list)
    args.total_num_fragment = total_num_fragment
    args.total_num_bcd = num_barcode
    global_dist_fp.write('mean_num_fragment_per_bcd\t%f\n' % args.mean_num_fragment_per_bcd)
    global_dist_fp.write('median_num_fragment_per_bcd\t%f\n' % args.median_num_fragment_per_bcd)
    global_dist_fp.write('total_num_fragment\t%d\n' % args.total_num_fragment)
    global_dist_fp.write('total_num_bcd\t%d\n' % args.total_num_bcd)

    args.read_per_bp_genome = args.gap_distance_lmda
    args.genome_length = calculate_genome_length(args.faidx_file)
    global_dist_fp.write('read_per_bp_genome\t%.20f\n' % args.read_per_bp_genome)
    global_dist_fp.write('genome_length\t%d\n' % args.genome_length)

    if args.is_wgs == False:
        args.target_region_length = calculate_bed_length(args.target_region_bed)
        global_dist_fp.write('target_region_length\t%d\n' % args.target_region_length)
        off_target_length = args.genome_length - args.target_region_length
        b = float(args.num_reads_ontarget) / float(args.num_reads_ontarget + args.num_reads_offtarget)

        args.read_per_bp_ontarget = b * float(args.genome_length) / args.target_region_length * args.read_per_bp_genome
        args.read_per_bp_offtarget = (1.0-b) * float(args.genome_length) / off_target_length * args.read_per_bp_genome
        global_dist_fp.write('read_per_bp_ontarget\t%.20f\n' % args.read_per_bp_ontarget)
        global_dist_fp.write('read_per_bp_offtarget\t%.20f\n' % args.read_per_bp_offtarget)

    return

def calculate_length_statistics(length_list):

    length_list.sort(reverse=True)
    total_length = float(sum(length_list))
    sum_length = 0

    N5_length = -1
    N25_length = -1
    N50_length = -1 
    N75_length = -1
    N95_length = -1

    for length in length_list:
        sum_length += length
        if N5_length  == -1 and sum_length > 0.05 * total_length: N5_length  = length
        if N25_length == -1 and sum_length > 0.25 * total_length: N25_length = length
        if N50_length == -1 and sum_length > 0.50 * total_length: N50_length = length
        if N75_length == -1 and sum_length > 0.75 * total_length: N75_length = length
        if N95_length == -1 and sum_length > 0.95 * total_length: N95_length = length

    return N5_length, N25_length, N50_length, N75_length, N95_length, total_length


def calculate_gap_distance_statistics(total_gap_distance_list):

    max_gap_distance = max(total_gap_distance_list)

    pmf = [0] * (max_gap_distance+1)
    cdf = [0] * (max_gap_distance+1)

    for d in total_gap_distance_list:
        if d < 0: 
            pmf[0] += 1
        else:
            pmf[d] += 1

    total_sum = sum(pmf)
    for i in range(0, len(pmf)):
        pmf[i] = float(pmf[i])/ total_sum

    cdf[0] = pmf[0]
    for i in range(1, len(pmf)):
        cdf[i] = cdf[i-1] + pmf[i]

    return pmf, cdf

if __name__ == '__main__':
    main()
