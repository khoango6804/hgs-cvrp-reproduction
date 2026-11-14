#include "LocalSearch.h"

#include <algorithm>
#include <ctime>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>

// A bounded post-processor that reuses the released HGS local search.
bool recreate(Individual& solution, std::mt19937& random, int iteration)
{
    const Params& params = *solution.params;
    auto& routes = solution.chromR;
    int anchor = std::uniform_int_distribution<int>(1, params.nbClients)(random);
    int count = std::min(params.nbClients, 4 + iteration % 9);
    std::vector<int> customers(params.nbClients);
    std::iota(customers.begin(), customers.end(), 1);
    std::partial_sort(customers.begin(), customers.begin() + count, customers.end(),
        [&](int a, int b) {
            return std::make_pair(params.timeCost[anchor][a], a)
                 < std::make_pair(params.timeCost[anchor][b], b);
        });
    customers.resize(count);
    std::vector<bool> removed(params.nbClients + 1, false);
    for (int node : customers) removed[node] = true;

    std::vector<double> loads(routes.size(), 0);
    for (std::size_t r = 0; r < routes.size(); ++r) {
        auto& route = routes[r];
        route.erase(std::remove_if(route.begin(), route.end(), [&](int node) { return removed[node]; }), route.end());
        for (int node : route) loads[r] += params.cli[node].demand;
    }
    std::shuffle(customers.begin(), customers.end(), random);
    for (int node : customers) {
        double demand = params.cli[node].demand;
        double best_delta = 1e30;
        std::size_t best_route = routes.size(), best_position = 0;
        for (std::size_t r = 0; r < routes.size(); ++r) {
            if (loads[r] + demand > params.vehicleCapacity) continue;
            const auto& route = routes[r];
            for (std::size_t p = 0; p <= route.size(); ++p) {
                int prev = p == 0 ? 0 : route[p - 1];
                int next = p == route.size() ? 0 : route[p];
                double delta = params.timeCost[prev][node] + params.timeCost[node][next] - params.timeCost[prev][next];
                if (delta < best_delta) {
                    best_delta = delta;
                    best_route = r;
                    best_position = p;
                }
            }
        }
        if (best_route == routes.size()) return false;
        routes[best_route].insert(routes[best_route].begin() + best_position, node);
        loads[best_route] += demand;
    }
    return true;
}

int main(int argc, char** argv)
{
    try {
        if (argc < 7) throw std::runtime_error("Expected instance, method, seconds, seed, output prefix and solutions");
        const std::string method = argv[2];
        if (method != "local-search" && method != "ruin-recreate") throw std::runtime_error("Unknown method");
        const double seconds = std::stod(argv[3]);
        const int seed = std::stoi(argv[4]);
        const std::string output = argv[5];
        Params params(argv[1], INT_MAX, seed);
        LocalSearch search(&params);
        std::mt19937 random(seed);
        std::vector<Individual> pool;
        for (int a = 6; a < argc; ++a) {
            Individual solution(&params);
            std::vector<std::vector<int>> routes;
            double cost;
            if (!Individual::readCVRPLibFormat(argv[a], routes, cost) || routes.size() > solution.chromR.size())
                throw std::runtime_error("Invalid input solution");
            std::copy(routes.begin(), routes.end(), solution.chromR.begin());
            solution.evaluateCompleteCost();
            if (!solution.isFeasible || solution.myCostSol.distance != cost)
                throw std::runtime_error("Input cost mismatch");
            pool.push_back(solution);
        }
        double best = 1e30;
        for (const auto& solution : pool) best = std::min(best, solution.myCostSol.distance);
        for (int i = 0; i < 120 && double(std::clock()) / CLOCKS_PER_SEC < seconds; ++i) {
            auto& parent = pool[i % pool.size()];
            Individual solution = parent;
            if (method == "ruin-recreate" && !recreate(solution, random, i)) continue;
            search.run(&solution, 1e6, 1e6);
            if (!solution.isFeasible) throw std::runtime_error("Infeasible local-search result");
            double cost = solution.myCostSol.distance;
            if (cost <= best * 1.005) solution.exportCVRPLibFormat(output + std::to_string(i) + ".sol");
            if (cost <= parent.myCostSol.distance) parent = solution;
            best = std::min(best, cost);
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    } catch (const std::string& error) {
        std::cerr << error << '\n';
        return 1;
    }
}
